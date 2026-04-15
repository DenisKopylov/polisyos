# P3 Core -> Fabric/Runtime Decoupling - Detailed Specification

- Status: Implemented
- Version: 1.1
- Effective phase: P3 (`2026-03-02` -> `2026-03-15`)
- Hard deadline for exception removal: `2026-04-30`
- Scope: `policy-engine`
- Owners: `team-core` (primary), `team-fabric`, `team-runtime`
- Related docs:
  - `p1_import_policy_v2_spec.md`
  - `p1_refactor_queue.md`
  - `import_debt_register.csv`
  - `import_exceptions.toml`
  - `import_exceptions_registry.md`
  - `arch_cycles_register.csv`
  - `src/polisyos/core/audit/README.md`
  - `src/polisyos/core/contracts/README.md`

## 1. Context and Problem Statement

Current P1 debt cluster for this phase:

1. `Q3` in `p1_refactor_queue.md` is open:
   - eliminate `core -> fabric/runtime` (`ARCH001-0033..0036`).
2. Active debt rows in `import_debt_register.csv`:
   - `ARCH001-0033`: `src/polisyos/core/audit/prov_json.py` (`core -> fabric`)
   - `ARCH001-0034`: `src/polisyos/core/audit/_assembler_core.py` (`core -> fabric`)
   - `ARCH001-0035`: `src/polisyos/core/audit/_assembler_core.py` (`core -> runtime`)
   - `ARCH001-0036`: `src/polisyos/core/audit/_assembler_provenance.py` (`core -> fabric`)
3. Active temporary exceptions:
   - `E-2026-02-CORE-FABRIC-001` (expires `2026-04-30`)
   - `E-2026-02-CORE-RUNTIME-001` (expires `2026-04-30`)
4. Import gate on `2026-02-09` reports no unmanaged violations, but these dependencies remain allowed only via temporary exceptions.
5. `CYCLE-001` (`core/fabric/ir/runtime`) remains open in `arch_cycles_register.csv`. P3 reduces one part of the cycle pressure but does not close the cycle alone.

Net effect: core audit infrastructure still depends on upper-layer packages (`fabric`, `runtime`), violating target DAG and keeping P1 debt unresolved.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Remove all production imports `polisyos.core.* -> polisyos.fabric.*` for provenance model usage.
2. Remove all production imports `polisyos.core.* -> polisyos.runtime.*` in audit assembly flow.
3. Move provenance graph model ownership to core-level contract surface.
4. Keep public behavior of audit export/verify stable (package structure, PROV-JSON semantics, integrity checks).
5. Remove `E-2026-02-CORE-FABRIC-001`, `E-2026-02-CORE-RUNTIME-001`, and close `ARCH001-0033..0036`.

### 2.2 Non-Goals (P3)

1. Full closure of `CYCLE-001` (requires additional `ir -> core` and related refactors).
2. Global redesign of runtime manifest schemas.
3. Rewriting Fabric provenance semantics or PROV relation model.
4. Major audit package feature additions unrelated to dependency cleanup.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Dependency direction after P3

Required direction:

1. `core` MUST depend only on `{core, ir, common}` according to import policy v2.
2. `fabric` and `runtime` MAY depend on `core`, but `core` MUST NOT import from `fabric` or `runtime`.
3. Provenance graph primitives shared across layers MUST be owned by `core` contract surface.

### 4.2 Canonical ownership

Canonical provenance model after P3:

| Current module | Canonical P3 module |
| --- | --- |
| `src/polisyos/fabric/provenance/core.py` | `src/polisyos/core/contracts/provenance.py` |

Expected exported symbols in canonical module:

- `EntityType`
- `ActivityType`
- `AgentType`
- `RelationType`
- `ProvenanceEntity`
- `ProvenanceActivity`
- `ProvenanceAgent`
- `ProvenanceEdge`
- `ProvenanceCoreGraph`
- `ProvenanceCoreRef`

### 4.3 Compatibility contract (one release)

For one release window after P3 merge:

1. Imports from `polisyos.fabric.provenance.core` SHOULD remain valid via thin compatibility re-export.
2. Compatibility module MUST NOT contain business logic or duplicate model implementations.
3. Canonical implementation remains single-source under `core`.

## 5. Detailed Technical Design

### 5.1 Provenance contract extraction

Required implementation:

1. Create `src/polisyos/core/contracts/provenance.py` with current provenance enums/dataclasses and graph methods.
2. Update `src/polisyos/core/contracts/__init__.py` and `__all__` to export provenance symbols.
3. Convert `src/polisyos/fabric/provenance/core.py` into compatibility re-export pointing to `core.contracts.provenance`.
4. Preserve exact serialization behavior:
   - `compute_stable_id()`
   - `to_dict()/from_dict()`
   - edge relation semantics and ordering.

Hard constraint:

1. Stable ID values for identical graph content MUST stay unchanged versus pre-P3 behavior.

### 5.2 Core audit import rewiring

Mandatory rewiring:

1. `src/polisyos/core/audit/prov_json.py`
   - replace imports from `polisyos.fabric.provenance.core` with `polisyos.core.contracts.provenance`.
2. `src/polisyos/core/audit/_assembler_provenance.py`
   - same provenance import replacement.
3. `src/polisyos/core/audit/_assembler_core.py`
   - provenance import replacement.
   - remove `RunManifest as LegacyRunManifest` import from `polisyos.runtime.manifest`.

### 5.3 Legacy runtime manifest detection without runtime import

Current behavior in `_assembler_core.py`:

1. Tries to parse `core.run.manifest.RunManifest`.
2. If failed, tries `runtime.manifest.RunManifest` only to emit explicit "legacy format unsupported" error.

P3 required behavior:

1. Keep equivalent error semantics without importing runtime package.
2. Add a local core-side shape detector helper (for example in `core/audit/_manifest_compat.py`):
   - parse JSON object,
   - detect legacy runtime-like shape (`schema_version` + `artifacts`, missing `registry_bundle`),
   - raise explicit legacy-not-supported message.
3. For unknown malformed manifests, keep generic unsupported-format error path.

### 5.4 Documentation updates

Required docs sync:

1. `src/polisyos/core/audit/README.md`
   - remove dependency note on `fabric.provenance.core` and `runtime.manifest`.
   - add dependency note on `core.contracts.provenance`.
2. `src/polisyos/core/contracts/README.md`
   - add provenance contract section and ownership rationale.
3. `src/polisyos/fabric/README.md` (or provenance docs)
   - mark provenance model source as core-owned with fabric facade.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-03-02` -> `2026-03-04`): Extract provenance contracts into `core.contracts.provenance`.
2. `M2` (`2026-03-04` -> `2026-03-08`): Rewire core audit imports and remove `core -> runtime` manifest import.
3. `M3` (`2026-03-09` -> `2026-03-12`): Add compatibility facade in fabric, update docs/tests.
4. `M4` (`2026-03-13` -> `2026-03-15`): Remove exceptions/debt entries, finalize evidence and freeze checks.

### 6.2 PR slicing (recommended)

1. `PR-A`: Add `core.contracts.provenance` and export surface.
2. `PR-B`: Rewire `core.audit` imports and introduce runtime-agnostic legacy manifest detector.
3. `PR-C`: Add fabric compatibility facade, update tests and docs.
4. `PR-D`: Remove exceptions/debt rows, mark queue status, run full freeze validation.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `import_exceptions.toml`
   - remove `E-2026-02-CORE-FABRIC-001`
   - remove `E-2026-02-CORE-RUNTIME-001`
2. `import_exceptions_registry.md`
   - mark/remove both exception IDs from active registry.
3. `import_debt_register.csv`
   - remove or mark closed: `ARCH001-0033..0036`.
4. `p1_refactor_queue.md`
   - mark `Q3` as `Done` with closure date.

### 7.2 Required verification commands

Architecture and freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p3_metrics \
  --summary-path .tmp/p3_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p3_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p3_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Targeted tests:

```bash
python3 -m pytest \
  tests/core/phase0/test_audit_export_verify.py \
  tests/fabric/test_provenance.py \
  tests/contract/test_golden_record_ids.py \
  tests/runtime/test_runtime_manifest_paths.py
```

Recommended new targeted tests for P3:

```bash
python3 -m pytest \
  tests/core/phase0/test_audit_manifest_compat.py \
  tests/core/phase0/test_provenance_contract_shims.py
```

## 8. Acceptance Criteria and DoD

P3 is complete only if all criteria are met:

1. `src/polisyos/core/**` has zero imports from `polisyos.fabric.*`.
2. `src/polisyos/core/**` has zero imports from `polisyos.runtime.*`.
3. `ARCH001-0033..0036` are absent from current import-gate output and debt register.
4. Exceptions `E-2026-02-CORE-FABRIC-001` and `E-2026-02-CORE-RUNTIME-001` are removed from active set.
5. Audit export/verify tests pass without behavior regression.
6. Provenance stable ID golden checks pass (no hash drift).
7. Blocking freeze comparison passes with no architecture regression.

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Stable ID drift after model move | High | Golden-record test on `compute_stable_id`, byte-for-byte serializer parity checks |
| False legacy-manifest detection | High | Explicit detector tests for core valid / runtime legacy / malformed payload cases |
| Compatibility break for Fabric imports | Medium | Thin re-export facade with same symbol names and types |
| Docs/governance drift from code changes | Medium | Treat exceptions/debt/docs updates as mandatory in same closure PR set |

## 10. Post-P3 Follow-Ups (Out of Scope)

1. Continue P1/P4 workstream for `ir -> core` (`ARCH001-0001..0028`) and closure of `CYCLE-001`.
2. Evaluate extraction of PROV-JSON converter into a dedicated core provenance package (`core.provenance`) to reduce coupling between `fabric.provenance.export_provo` and `core.audit`.
3. Tighten compatibility window and remove fabric provenance shim in a scheduled deprecation release.

## 11. Baseline Snapshot for P3 Planning (`2026-02-09`)

From `collect_arch_metrics.py` run:

- `package_cycles_count = 2`
- `import_violations_count = 0` (with active temporary exceptions)
- `test_collect_errors_count = 42`
- `ruff_total_issues = 1213`
- `stale_sources_missing_paths_count = 40`

From `lint_imports.py`:

- Active allowed exceptions include `E-2026-02-CORE-FABRIC-001` and `E-2026-02-CORE-RUNTIME-001`.
- No unmanaged `ARCH001` violations.

## 12. Implementation Evidence (`2026-02-09`)

### 12.1 Runtime and import-boundary outcomes

1. Provenance model moved to canonical core contract module:
   - `src/polisyos/core/contracts/provenance.py`
2. Fabric provenance module converted to compatibility facade:
   - `src/polisyos/fabric/provenance/core.py`
3. Core audit modules rewired from `fabric.provenance.core` to `core.contracts.provenance`:
   - `src/polisyos/core/audit/prov_json.py`
   - `src/polisyos/core/audit/_assembler_core.py`
   - `src/polisyos/core/audit/_assembler_provenance.py`
4. Removed runtime manifest dependency from core audit:
   - deleted `polisyos.runtime.manifest` import from `src/polisyos/core/audit/_assembler_core.py`
   - added shape-based legacy detector in `src/polisyos/core/audit/_manifest_compat.py`
5. Removed residual `core -> fabric` import in security backend:
   - `src/polisyos/core/security/db_backend.py` no longer type-imports `polisyos.fabric.io.db`.

### 12.2 Debt and governance artifacts updated

1. Removed exceptions:
   - `E-2026-02-CORE-FABRIC-001`
   - `E-2026-02-CORE-RUNTIME-001`
   from:
   - `import_exceptions.toml`
   - `import_exceptions_registry.md`
2. Removed debt rows:
   - `ARCH001-0033`
   - `ARCH001-0034`
   - `ARCH001-0035`
   - `ARCH001-0036`
   from `import_debt_register.csv`.
3. Updated `Q3` status to Done in `p1_refactor_queue.md`.

### 12.3 Documentation updates

1. `src/polisyos/core/audit/README.md` updated to core-owned provenance dependency.
2. `src/polisyos/core/contracts/README.md` updated with provenance contracts section.
3. `src/polisyos/fabric/README.md` updated to describe provenance `core.py` as compatibility facade.

### 12.4 Verification results

Import gate (`lint_imports.py`, `2026-02-09`):

- `Violations: none`
- Allowed exceptions list no longer contains `E-2026-02-CORE-FABRIC-001` / `E-2026-02-CORE-RUNTIME-001`.

Architecture metrics (`collect_arch_metrics.py`, `2026-02-09T20:52:18Z`):

- `package_cycles_count = 2`
- `import_violations_count = 0`
- `test_collect_errors_count = 42`

Freeze comparison:

- `compare_baseline.py --mode blocking` -> `[OK] Architecture freeze checks passed.`

Targeted tests:

- `37 passed`:
  - `tests/core/phase0/test_audit_export_verify.py`
  - `tests/fabric/test_provenance.py`
  - `tests/contract/test_golden_record_ids.py`
  - `tests/runtime/test_runtime_manifest_paths.py`
  - `tests/core/phase0/test_audit_manifest_compat.py`
  - `tests/core/phase0/test_provenance_contract_shims.py`
