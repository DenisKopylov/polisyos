# P2 Lex <-> Scientist Decoupling - Detailed Specification

- Status: Implemented
- Version: 1.1
- Effective phase: P2 (`2026-02-16` -> `2026-03-01`)
- Hard deadline for exception removal: `2026-04-30`
- Scope: `policy-engine`
- Owners: `team-lex` (primary), `team-scientist`, `team-core`
- Related docs:
  - `p1_import_policy_v2_spec.md`
  - `p1_refactor_queue.md`
  - `import_debt_register.csv`
  - `import_exceptions.toml`
  - `import_exceptions_registry.md`
  - `arch_cycles_register.csv`

## 1. Context and Problem Statement

Current architecture debt cluster:

1. Cycle `CYCLE-003` is open in `arch_cycles_register.csv`:

   - `polisyos.lex <-> polisyos.scientist`
2. `ARCH001-0029..0032` are active in `import_debt_register.csv`:

   - `src/polisyos/lex/simulator/engine.py` imports:
     - `polisyos.scientist.governance.passes.base`
     - `polisyos.scientist.governance.passes.legal_pass`
     - `polisyos.scientist.governance.passes.safety_pass`
     - `polisyos.scientist.governance.profiles`
3. Exception `E-2026-02-LEX-SCIENTIST-001` temporarily permits these imports until `2026-04-30`.
4. Reverse dependency remains valid and intentional:

   - `src/polisyos/scientist/nodes/builtins/governance/legal_check.py` imports `polisyos.lex.*`.

Net effect: lower layer `lex` depends on higher layer `scientist`, violating target DAG and blocking closure of one package cycle.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Remove all runtime imports `lex -> scientist` from production code.
2. Break `CYCLE-003` without changing legal evaluation semantics.
3. Move shared governance abstractions to a neutral layer under `core`.
4. Keep `scientist` as orchestration layer, not the source of shared validation primitives.
5. Remove exception `E-2026-02-LEX-SCIENTIST-001` and close related debt records.

### 2.2 Non-Goals (P2)

1. Full redesign of Scientist governance pipeline (`preflight`, `postflight`, orchestration).
2. Rewriting legal backends logic (`expr_ast`, `stub`) beyond relocation/import rewiring.
3. Removal of `scientist -> lex` dependency in governance node `legal_check` (this direction is allowed by policy).

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Dependency direction after P2

Required direction:

1. `lex` MAY import `core`, `ir`, `fabric`, `common` (as in policy v2), and MUST NOT import `scientist`.
2. `scientist` MAY import `lex` for orchestration use cases.
3. Shared validation/pass contracts MUST live in `polisyos.core.governance.*`.

Target dependency shape:

`common -> core -> (lex, scientist)` and optional `scientist -> lex`, with no `lex -> scientist`.

### 4.2 Canonical package ownership

The following modules become canonical in `core`:

| Current module (source of shared logic)                        | Canonical P2 module                                       |
| -------------------------------------------------------------- | --------------------------------------------------------- |
| `src/polisyos/scientist/governance/profiles.py`                | `src/polisyos/core/governance/profiles.py`                |
| `src/polisyos/scientist/governance/passes/base.py`             | `src/polisyos/core/governance/passes/base.py`             |
| `src/polisyos/scientist/governance/passes/legal_pass.py`       | `src/polisyos/core/governance/passes/legal_pass.py`       |
| `src/polisyos/scientist/governance/passes/safety_pass.py`      | `src/polisyos/core/governance/passes/safety_pass.py`      |
| `src/polisyos/scientist/governance/legal/ast_policy.py`        | `src/polisyos/core/governance/legal/ast_policy.py`        |
| `src/polisyos/scientist/governance/legal/backends/base.py`     | `src/polisyos/core/governance/legal/backends/base.py`     |
| `src/polisyos/scientist/governance/legal/backends/stub.py`     | `src/polisyos/core/governance/legal/backends/stub.py`     |
| `src/polisyos/scientist/governance/legal/backends/expr_ast.py` | `src/polisyos/core/governance/legal/backends/expr_ast.py` |

Modules that remain Scientist-owned:

- `src/polisyos/scientist/governance/pipeline.py`
- `src/polisyos/scientist/governance/preflight.py`
- `src/polisyos/scientist/governance/postflight.py`
- `src/polisyos/scientist/governance/telemetry.py`
- `src/polisyos/scientist/governance/report.py`
- Scientist-specific passes that are not reused by Lex in P2 (`budget`, `schema`, `privacy`, `pii_check`, `quality_gate`, `confidence`, `equity`).

### 4.3 Compatibility contract (one release)

For one release window after P2 merge:

1. Old imports under `polisyos.scientist.governance.profiles` and `polisyos.scientist.governance.passes.{base,legal_pass,safety_pass}` MUST continue to resolve.
2. These legacy modules MUST be thin re-export shims to `polisyos.core.governance.*` and MUST NOT contain business logic.
3. Legacy shims SHOULD emit `DeprecationWarning` once per process.
4. Shim removal target MUST be tracked as P2 follow-up with explicit due date.

## 5. Detailed Technical Design

### 5.1 New/updated public API

Canonical API surface:

1. `polisyos.core.governance.profiles`

   - `ProfileLevel`
   - `ValidationProfile`
2. `polisyos.core.governance.passes.base`

   - `PassContext`
   - `ValidatorPass`
3. `polisyos.core.governance.passes.legal_pass`

   - `LegalPass`
4. `polisyos.core.governance.passes.safety_pass`

   - `SafetyPass`
5. `polisyos.core.governance.legal.backends`

   - `RuleBackend` adapter exports and concrete backends

No DTO/schema changes are permitted in this phase for:

- `polisyos.core.contracts.lex.ComplianceIssue`
- `polisyos.core.contracts.lex.IssueSeverity`
- `polisyos.core.contracts.lex.RuleBackend`

### 5.2 Required call-site rewiring

Mandatory import rewiring:

1. `src/polisyos/lex/simulator/engine.py`

   - Replace all imports from `polisyos.scientist.governance.*` with `polisyos.core.governance.*`.
2. `src/polisyos/core/components/_cli_lex.py`

   - Replace runtime import target `polisyos.scientist.governance.profiles` with `polisyos.core.governance.profiles`.
3. `src/polisyos/scientist/governance/preflight.py`

   - Import shared `PassContext`, `LegalPass`, `SafetyPass`, `ValidationProfile` from `core.governance`.
4. `src/polisyos/scientist/nodes/builtins/governance/run_governance.py`

   - Import shared `PassContext` and `ValidationProfile` from `core.governance`.
5. Tests and docs:

   - Update imports in tests that directly target moved modules.
   - Update references in `src/polisyos/lex/README.md`, `src/polisyos/scientist/README.md`, and `src/polisyos/scientist/governance/README.md`.

### 5.3 Rules for preventing regression

1. `src/polisyos/lex/**` MUST NOT import any module matching `polisyos.scientist.*`.
2. Any new shared pass or profile reused outside Scientist MUST be introduced in `core.governance`, not under `scientist.governance`.
3. Dynamic imports (`importlib.import_module`) MUST follow the same boundary contract and are subject to architecture review.

## 6. Migration Plan (2 Weeks)

### 6.1 Workstream and milestones

1. `M1` (`2026-02-16` -> `2026-02-18`): Extract shared governance primitives to `core.governance`.
2. `M2` (`2026-02-18` -> `2026-02-21`): Rewire Lex and Scientist call-sites to canonical imports.
3. `M3` (`2026-02-22` -> `2026-02-24`): Add compatibility shims and deprecation notices.
4. `M4` (`2026-02-25` -> `2026-03-01`): Remove temporary exception/debt entries, finalize docs, close cycle evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: Add `core.governance` package + migrate shared modules + add direct unit tests.
2. `PR-B`: Rewire runtime call-sites (`lex`, `scientist`, `core/components`) and update affected tests.
3. `PR-C`: Add/verify compatibility shims; update docs and debt registries.
4. `PR-D`: Governance cleanup (remove exception, close cycle records, run freeze checks).

## 7. CI and Governance Updates

### 7.1 Artifacts to update as part of completion

1. `import_exceptions.toml`

   - Remove `E-2026-02-LEX-SCIENTIST-001`.
2. `import_exceptions_registry.md`

   - Mark/remove the same exception from active set.
3. `import_debt_register.csv`

   - Remove/close `ARCH001-0029..0032`.
4. `arch_cycles_register.csv`

   - Mark `CYCLE-003` as closed with closure evidence reference.

### 7.2 Required verification commands

Architecture and freeze checks (repository root):

```bash
python3 tools/quality/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p2_metrics \
  --summary-path .tmp/p2_metrics/summary.json \
  --print-summary

python3 tools/quality/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p2_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p2_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Targeted tests:

```bash
python3 -m pytest \
  tests/unit/lex/simulator/test_engine.py \
  tests/unit/scientist/governance/test_legal_pass.py \
  tests/unit/scientist/governance/test_validation_pipeline.py \
  tests/unit/core/test_backend_dispatcher.py
```

## 8. Acceptance Criteria and DoD

P2 is complete only if all criteria are met:

1. `lex` has zero imports from `polisyos.scientist.*`.
2. `ARCH001-0029..0032` do not appear in current import gate output.
3. `CYCLE-003` is absent from current package cycle report.
4. `E-2026-02-LEX-SCIENTIST-001` is removed from active exceptions.
5. Legacy import paths in `scientist.governance` still work (one-release shim period).
6. `NormImpactAnalyzer` behavior remains equivalent on existing test corpus.
7. Freeze blocking check passes with no architecture regression.

## 9. Risks and Mitigations

| Risk                                                         | Impact | Mitigation                                                                               |
| ------------------------------------------------------------ | ------ | ---------------------------------------------------------------------------------------- |
| API break for existing imports from `scientist.governance.*` | High   | Provide shim modules + deprecation warnings for one release                              |
| Semantics drift during module move                           | High   | Move code with minimal edits first, then rewire imports; compare test outputs            |
| Hidden dynamic import path remains stale                     | Medium | Grep for `importlib.import_module(\"polisyos.scientist.governance` and rewire explicitly |
| Debt artifacts not synchronized with code closure            | Medium | Treat registry/debt/cycle updates as mandatory in same PR set                            |

## 10. Post-P2 Follow-Ups (Out of Scope for this spec)

1. Evaluate migration of additional reusable passes (`budget`, `quality_gate`, `confidence`) into `core.governance` if shared by more than one root.
2. Tighten import policy for `packs` and review whether long-term `scientist -> lex` should stay broad or be narrowed by contract APIs.
3. Remove compatibility shims after agreed deprecation window with explicit release note.

## 11. Implementation Evidence (`2026-02-09`)

### 11.1 Runtime and import boundary outcomes

1. `src/polisyos/lex/simulator/engine.py` migrated to `polisyos.core.governance.*` imports.
2. `src/polisyos/core/components/_cli_lex.py` now resolves profiles from `polisyos.core.governance.profiles`.
3. Scientist orchestration (`preflight`, `pipeline`, `postflight`, `run_governance`) uses shared contracts from `core.governance` while keeping orchestration logic in `scientist`.
4. Legacy paths under `polisyos.scientist.governance.{profiles,passes.base,passes.legal_pass,passes.safety_pass,legal.*}` remain as compatibility shims with deprecation warnings.

### 11.2 Debt and governance artifacts updated

1. Removed exception `E-2026-02-LEX-SCIENTIST-001` from:

   - `import_exceptions.toml`
   - `import_exceptions_registry.md`
2. Removed debt rows `ARCH001-0029..0032` from `import_debt_register.csv`.
3. Marked cycle `CYCLE-003` as `closed` in `arch_cycles_register.csv`.
4. Updated `p1_refactor_queue.md` (`Q2`, `Q4`) to `Done`.

### 11.3 Verification results

Architecture metrics (`collect_arch_metrics.py`, run at `2026-02-09T20:35:18Z`):

- `package_cycles_count = 2` (baseline `3`)
- `import_violations_count = 0` (baseline `36`)
- `test_collect_errors_count = 42` (baseline `42`)

Blocking freeze comparison:

- `compare_baseline.py --mode blocking` -> `[OK] Architecture freeze checks passed.`

Targeted tests:

- `45 passed`:
  - `tests/unit/lex/simulator/test_engine.py`
  - `tests/unit/scientist/governance/test_legal_pass.py`
  - `tests/unit/scientist/governance/test_validation_pipeline.py`
  - `tests/unit/scientist/governance/test_shared_shims.py`
  - `tests/unit/core/test_backend_dispatcher.py`
  - `tests/unit/fabric/test_quality_indicators.py`
  - `tests/unit/fabric/connectors/test_quality_system.py::TestQualityGateIntegration::test_quality_gate_blocks_bronze_in_strict`
