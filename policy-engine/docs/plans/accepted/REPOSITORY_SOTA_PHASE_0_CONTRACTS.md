---
title: Repository SOTA Phase 0 Contracts
status: active
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-05-02
stability: baseline
---

# Repository SOTA Phase 0 Contracts

This note replaces the temporary freeze-safety execution posture for
`REPOSITORY_SOTA_PLAN.md`. Phase 0 is now a full contract-normalization
baseline: architecture policy is machine-readable, current implementation
surfaces are registered, and report-only debt is recorded before later topology
migrations.

## Contract Validation Baseline

Validated locally on 2026-05-02:

| Contract | Schema | Result |
| --- | --- | --- |
| `architecture/topology.toml` | `schemas/topology/topology.schema.json` | OK |
| `architecture/package_boundaries.toml` | `schemas/topology/package_boundaries.schema.json` | OK |
| `architecture/import_contracts.toml` | `schemas/topology/import_contracts.schema.json` | OK |
| `architecture/shims.toml` | `schemas/topology/migration_shims.schema.json` | OK |
| `architecture/complexity_exceptions.toml` | `schemas/topology/complexity_exceptions.schema.json` | OK |
| `architecture/guardrail_exceptions.toml` | `schemas/topology/guardrail_exceptions.schema.json` | OK |
| `architecture/public_surface.toml` | `schemas/topology/public_surface.schema.json` | OK |
| `architecture/generated_artifacts.toml` | `schemas/topology/generated_artifacts.schema.json` | OK |
| `architecture/domain_migration_batches.toml` | `schemas/topology/domain_migration_batches.schema.json` | OK |
| `architecture/conservative_overlay.toml` | `schemas/topology/conservative_overlay.schema.json` | OK |

`architecture/conservative_overlay.toml` is retained only as a historical
record. Its status is `closed`, its end gate is no longer event-gated, and it is
not an active execution constraint.

## ADR Validation

ADR-0111 through ADR-0128 remain the target architecture set. No superseding ADR
is required, but implementation notes were added where repository reality
needed clarification:

| ADR | Phase 0 validation result |
| --- | --- |
| ADR-0111 | Workspace/product-root boundary remains valid and is reflected in `architecture/topology.toml`. |
| ADR-0112 | Data Forge read API and contract schemas are now registered in generated-artifact policy. |
| ADR-0113 | Asset-centric pipeline posture remains valid; Data Forge contract schemas are tracked as committed outputs. |
| ADR-0114 | Schema-registry posture remains valid; topology schemas now cover all `architecture/*.toml` contracts. |
| ADR-0115 | Layer contract is schema-valid; the architecture TOML import-linter runner remains a report-only target until its baseline is accepted. |
| ADR-0116 | No observability contract conflict found during Phase 0. |
| ADR-0117 | No SecretBackend contract conflict found during Phase 0; security scan remains report-only baseline debt. |
| ADR-0118 | Release-train and SemVer posture remains valid; release paths are covered by CODEOWNERS. |
| ADR-0119 | Current product-root `packages/` is registered as transitional committed source, not as a replacement for the target frontend workspace. |
| ADR-0120 | Test-topology mirror posture remains valid; no structural test moves are performed in Phase 0. |
| ADR-0121 | Python workspace posture remains valid; no workspace dependency gate is tightened in Phase 0. |
| ADR-0122 | Lakehouse snapshot posture remains valid; Data Forge manifest schemas are registered. |
| ADR-0123 | ArtifactRef governance posture remains valid; ArtifactRef JSON Schema is registered. |
| ADR-0124 | LLM idempotency posture remains valid; no prompt/cache contract change in Phase 0. |
| ADR-0125 | Data quality regime posture remains valid; quality/security findings stay report-only until exceptions or cleanup phases are recorded. |
| ADR-0126 | Docs lifecycle posture remains valid; docs freshness debt is captured as report-only output. |
| ADR-0127 | Gate posture is baseline-first: architecture guardrails pass, docs/security remain report-only debt. |
| ADR-0128 | No reproducibility contract change in Phase 0. |

## Normalized Registries

Phase 0 normalized these contract surfaces:

- Topology now classifies current product-root config/source surfaces:
  `basedpyright.toml`, `architecture/baselines/basedpyright/`, `.cursor/`,
  `packages/`, `.markdownlint-cli2.jsonc`, `.taplo.toml`, `.yamllint`, and
  `CHANGELOG-DESIGN.md`.
- Package boundaries and import contracts now register
  `polisyos.berl`, `polisyos.calibration`, `polisyos.ddm_15_7`, and
  `polisyos.synthetic_world`.
- Public surface now classifies every top-level `src/polisyos/*/__init__.py`
  package; `polisyos.ddm_15_7` is explicitly `internal`.
- Generated artifacts now include Data Forge artifact and manifest JSON
  Schemas under `schemas/artifacts/` and `schemas/manifests/`.
- Guardrail exceptions now have a schema-backed empty-baseline registry:
  `architecture/guardrail_exceptions.toml`.
- CODEOWNERS now covers repo-root control files and every committed
  product-root topology path.
- Public-surface and generated-artifact reference outputs were regenerated via
  `uv run polisyos-tools architecture guardrails sync --skip-deep-import-baseline`.

## Shim Normalization Baseline

All 23 compatibility shims in `architecture/shims.toml` have:

- owner
- reason
- target path
- sunset date
- issue/evidence pointer

The root research script shims are now classified as `file_relocation` because
Phase -1.5 moved their durable implementations into `tools/research/`.

## Report-Only Gate Baseline

| Gate area | Phase 0 command or evidence | Result | Enforcement posture |
| --- | --- | --- | --- |
| Schema validation | Local JSON Schema validation for all architecture TOMLs | OK | Baseline accepted |
| Public surface / generated artifacts / deep imports | `uv run polisyos-tools architecture guardrails check` | OK | Existing architecture guardrail may remain fail-closed because baseline is current |
| Migration shims | Local shim metadata audit | OK: 23 checked, 0 missing metadata | Baseline accepted |
| Guardrail exceptions | Schema validation plus architecture guardrail check | OK: no active exceptions | Baseline accepted |
| Topology loose/local state | Git ignore classification for `.venv-spatial-tests/`, `topics.csv`, and `policy-engine/all_1000_policy_topics.csv` | Ignored local state | Report-only until fixture/source decision |
| Import contracts | Schema-valid `architecture/import_contracts.toml` | OK | Report-only for the architecture TOML import-linter runner |
| Docs freshness | `uv run polisyos-tools validation check-docs-accuracy --repo-root .` | 56 existing violations | Report-only debt; no new fail-closed gate |
| Security scan | `uv run ruff check --select S --exit-zero --statistics .` | 99 findings by current Ruff S baseline | Report-only debt; no new fail-closed gate |

Phase 0 did not add or tighten CI workflow gates. Existing `.github/workflows`
checks are left as-is; new fail-closed gates must not be added until their
baseline output and exceptions are recorded.

## Structural Move Evidence Template

Every later structural move must carry this evidence before execution:

| Field | Required value |
| --- | --- |
| Move id | Stable id used in plan, review, and rollback notes |
| Source path | Exact current path |
| Target path | Exact intended canonical path |
| Owner | Logical owner and reviewer |
| Risk class | `docs-only`, `compat-wrapper`, `source-move`, `data-fixture`, `generated-output`, or `runtime-facing` |
| Compatibility shim | Existing shim id, new shim id, or explicit `not needed` reason |
| Evidence requirement | Tests, schema validation, import baseline, generated-artifact check, docs update, or manual review |
| Rollback note | Restore source path, remove/disable target path, restore shim state, and rerun listed evidence |

## Rollback Note Template

For each accepted move, attach a rollback note with:

1. Move id and owner.
2. Source and target paths.
3. Files intentionally edited.
4. Compatibility shim state before and after the move.
5. Commands or checks that proved the move.
6. Exact rollback sequence.
7. Residual risk and follow-up issue.

## Acceptance Status

- Architecture contracts validate locally.
- Public-surface and generated-artifact baseline outputs are current.
- Existing compatibility shims have owner, reason, target, sunset, and issue or
  exception evidence.
- The temporary conservative overlay is closed.
- No structural moves are performed by this Phase 0 note.
- No new report-only debt is made fail-closed in Phase 0.
