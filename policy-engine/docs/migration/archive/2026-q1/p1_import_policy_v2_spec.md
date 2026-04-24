# P1 Import Policy v2 — Detailed Specification

- Status: Implemented (P1 execution baseline)
- Version: 1.0
- Effective phase: P1 (`2026-02-10` -> `2026-04-30`)
- Scope: `policy-engine`
- Owners: `team-core` (policy/tooling), `team-ir`, `team-lex`, `team-scientist`
- Related docs:
  - `p0_baseline_freeze.md`
  - `freeze_policy.md`
  - `p1_refactor_queue.md`
  - `docs/adr/0004-architecture-boundaries-import-gate.md`

## 1. Context and Problem Statement

P0 freeze is completed and blocks architecture regressions, but the import policy remains at `v1` and does not fully encode the P1 migration contract.

Baseline (captured on `2026-02-09`, reported as `baseline_2026-02-10.md`):

- `package_cycles_count = 3`
- `import_violations_count = 36`
- `test_collect_errors_count = 42`
- `ruff_total_issues = 1194`
- `stale_sources_missing_paths_count = 40`

Top P1 import debt clusters (from `import_debt_register.csv` and `arch_cycles_register.csv`):

- `ir -> core` (`ARCH001-0001..0028`)
- `lex -> scientist` (`ARCH001-0029..0032`, `CYCLE-003`)
- `core -> fabric/runtime` (`ARCH001-0033..0036`)
- package cycle `CYCLE-001` (`core/fabric/ir/runtime`)

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Define a single normative import contract for P1 as `Import Policy v2`.
2. Preserve no-regression guarantees introduced in P0.
3. Convert import debt from “implicit technical noise” into managed, expiring exceptions.
4. Keep migration incremental: no big-bang module rewrites in P1.

### 2.2 Non-goals (P1)

1. Full cleanup of all architecture debt to zero in one iteration.
2. Global external dependency allowlist for every root (beyond current IR focus).
3. Re-design of domain models unrelated to import boundaries.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Source of Truth and Affected Artifacts

`Import Policy v2` is defined by the following artifact set:

1. `import_policy.toml` (versioned policy matrix).
2. `import_exceptions.toml` (temporary and expiring exceptions).
3. `import_exceptions_registry.md` (human-readable registry of active exceptions).
4. `import_debt_register.csv` (debt ownership and exception mapping).
5. `tools/lint/lint_imports.py` (AST-based policy enforcement).
6. `tools/lint/collect_arch_metrics.py` (snapshot generation).
7. `tools/lint/compare_baseline.py` (freeze/no-regression and exception checks).
8. `.github/workflows/arch-freeze.yml` (CI enforcement entrypoint).

All artifacts MUST stay logically consistent.

## 5. P1 Layer Contract (v2 Dependency Matrix)

### 5.1 Internal roots

Known roots for P1:

- `common`
- `ir`
- `core`
- `fabric`
- `foundry`
- `runtime`
- `lex`
- `scholar`
- `scientist`
- `packs`

### 5.2 Allowed internal imports by root

P1 matrix (target for `import_policy.toml` `version = "2"`):

| source root | allowed target roots                                                                  |
| ----------- | ------------------------------------------------------------------------------------- |
| `common`    | `common`                                                                              |
| `ir`        | `ir`                                                                                  |
| `core`      | `core`, `ir`, `common`                                                                |
| `fabric`    | `fabric`, `core`, `ir`, `common`                                                      |
| `foundry`   | `foundry`, `core`, `ir`, `common`                                                     |
| `runtime`   | `runtime`, `core`, `ir`, `common`                                                     |
| `lex`       | `lex`, `fabric`, `ir`, `core`, `common`                                               |
| `scholar`   | `scholar`, `fabric`, `ir`, `core`, `common`                                           |
| `scientist` | `scientist`, `lex`, `scholar`, `foundry`, `fabric`, `runtime`, `core`, `ir`, `common` |
| `packs`     | `*` (transitional for P1, tighten in P2)                                              |

Notes:

1. `ir` remains self-contained at runtime imports in P1.
2. Cross-root imports into underscored internals are forbidden unless exceptioned.
3. `packs` is intentionally broad in P1 to avoid blocking domain delivery during migration.

### 5.3 External imports

For P1, strict external policy is enforced for `ir`:

- stdlib is always allowed.
- additional allowlist: `pydantic`, `typing_extensions`, `yaml`.

External policy for other roots MAY be introduced in P2.

## 6. Violation Semantics (Rule Catalog)

`lint_imports.py` MUST enforce the following rule set:

1. `ARCH001`: forbidden cross-root internal import (matrix violation).
2. `ARCH002`: forbidden external import in `ir` outside allowlist.
3. `ARCH003`: forbidden cross-root import from `_legacy` namespaces.
4. `ARCH004`: forbidden deep import into `polisyos.fabric.world.store*` / `materialize*` from non-fabric-world sources.
5. `ARCH005`: forbidden imports of legacy fabric internals (`fabric.io.graph_store`, `fabric.materializer`, `fabric.schema`, `fabric.udf`) outside fabric.
6. `ARCH006`: forbidden cross-root import into private/internal subpackages (underscored path segments).

Cycle policy:

1. Package cycles MUST be reported from runtime import graph.
2. CI blocking mode MUST fail when cycles are present (`--fail-on-cycles` in metric collection).
3. P1 success criteria require no growth of cycle count relative to baseline.

`TYPE_CHECKING` behavior:

1. Metric collection keeps `--allow-type-checking` enabled to avoid runtime false positives during migration.
2. New runtime imports MUST NOT be hidden under `TYPE_CHECKING` as a permanent bypass.

## 7. Exception Model (Temporary Debt Permit)

Exceptions are technical debt permits, not waivers.

### 7.1 Mandatory fields

Each `[[exception]]` MUST include:

- `id`
- `owner`
- `reason`
- `expires`
- `source_glob`

At least one selector MUST be present:

- `import_root`, or
- `import_module_prefix`, or
- `external_module`

Optional selector:

- `source_module_prefix`

### 7.2 Validity rules

1. `expires` MUST be ISO date `YYYY-MM-DD`.
2. `expires` MUST be within 90 days from PR check date.
3. Expired exceptions MUST block merge.
4. Duplicate exception IDs MUST block merge.
5. Every exception ID MUST exist in `import_exceptions_registry.md`.
6. `external_module` MUST NOT be combined with internal selectors (`import_root`, `import_module_prefix`).

### 7.3 ID convention (recommended)

Recommended format:

`E-YYYY-MM-<SOURCE>-<TARGET>-NNN`

Example:

`E-2026-02-LEX-SCIENTIST-001`

### 7.4 Operational SLA

1. Every exception SHOULD map to one or more entries in `import_debt_register.csv`.
2. Owner team MUST remove or renew (with explicit justification) before expiry.
3. Renewals SHOULD shorten scope (`source_glob` / prefix) instead of expanding it.

## 8. CI and Governance Contract

### 8.1 Mandatory pipeline behavior

In `.github/workflows/arch-freeze.yml`:

1. `collect-metrics` MUST produce `import_gate.txt`, `test_collect.txt`, `compileall.txt`, `ruff_stats.txt`, `stale_sources_missing_paths.txt`, `summary.json`.
2. `compare` dry-run MUST always execute.
3. `compare` blocking MUST execute on `pull_request`.

### 8.2 Blocking conditions in P1

PR MUST fail when at least one of the following is true:

1. `delta_package_cycles > 0`
2. `delta_import_violations > 0`
3. `delta_test_collect_errors > 0`
4. malformed/expired/overlong exception horizon
5. exception missing in registry
6. new deep-import findings (`ARCH004` / `ARCH006`) versus baseline `import_gate.txt`
7. `current.import_violations_count > 0` (unmanaged violations are forbidden in v2)
8. active exception ID is missing in `import_debt_register.csv:exception_id`

## 9. Rollout Plan for P1 Import Policy v2

### 9.1 Milestones

1. `M1` (`2026-02-10` -> `2026-02-12`): approve this spec and ADR update for v2.
2. `M2` (`2026-02-12` -> `2026-02-14`): align `import_policy.toml` to `version = "2"` and matrix above.
3. `M3` (`2026-02-14` -> `2026-02-18`): ensure `lint_imports.py` behavior is policy-driven and compatible with v2 contract.
4. `M4` (`2026-02-18` -> `2026-04-30`): execute P1 queue (`Q2`, `Q3`, `Q4`, `Q5`, plus `CYCLE-001` workstream).

### 9.2 Workstream mapping

| queue item                     | policy impact                                          |
| ------------------------------ | ------------------------------------------------------ |
| `Q2` `lex <-> scientist` cycle | eliminates `ARCH001-0029..0032`, closes `CYCLE-003`    |
| `Q3` `core -> fabric/runtime`  | eliminates `ARCH001-0033..0036`                        |
| `Q5` `ir -> core`              | eliminates `ARCH001-0001..0028`                        |
| `CYCLE-001`                    | reduces package cycle debt in `core/fabric/ir/runtime` |

### 9.3 Exit criteria (P1 close on `2026-04-30`)

1. No open high-severity P1 items in `import_debt_register.csv` past due date.
2. No expired exception entries.
3. No increase in freeze-gate metrics relative to baseline.
4. Architecture owners confirm Go for post-P1 tightening (P2).

## 10. Definition of Done for Import Policy v2

`Import Policy v2` is considered implemented when all are true:

1. `import_policy.toml` is set to policy version `2` and reflects section 5 matrix.
2. CI enforces section 8 blocking conditions in PR.
3. Exception lifecycle rules in section 7 are active and verified.
4. P1 queue ownership is explicit for all ARCH001 clusters and cycle items.
5. Evidence artifacts are reproducible via `collect_arch_metrics.py`.

## 11. Risks and Mitigations

| risk                                            | impact | mitigation                                                           |
| ----------------------------------------------- | ------ | -------------------------------------------------------------------- |
| Over-broad exceptions become de-facto permanent | high   | enforce 90-day cap, owner accountability, registry checks            |
| Policy/tool drift                               | high   | treat TOML + linter + compare script as single contract in every PR  |
| Freeze fatigue from noisy baseline              | medium | keep no-regression gate strict, prioritize high-severity queues only |
| Hidden coupling via deep imports                | high   | maintain ARCH004/ARCH006 diff checks against baseline                |

## 12. Appendix A — Reference Policy v2 Skeleton

```toml
[policy]
version = "2"
internal_prefix = "polisyos"
src_root = "src"

[roots]
known = ["common","ir","core","fabric","foundry","scientist","runtime","scholar","lex","packs"]

[internal.allow]
common = ["common"]
ir = ["ir"]
core = ["core","ir","common"]
fabric = ["fabric","core","ir","common"]
foundry = ["foundry","core","ir","common"]
scientist = ["scientist","lex","scholar","foundry","fabric","runtime","core","ir","common"]
runtime = ["runtime","core","ir","common"]
scholar = ["scholar","fabric","ir","core","common"]
lex = ["lex","fabric","ir","core","common"]
packs = ["*"]

[external.allow.ir]
modules = ["pydantic","typing_extensions","yaml"]
```

## 13. Appendix B — Exception Entry Template

```toml
[[exception]]
id = "E-2026-02-LEX-SCIENTIST-001"
owner = "team-lex"
reason = "Temporary adapter during governance boundary extraction"
expires = "2026-03-31"
source_glob = "src/polisyos/lex/**"
import_root = "scientist"
source_module_prefix = "polisyos.lex.simulator"
```
