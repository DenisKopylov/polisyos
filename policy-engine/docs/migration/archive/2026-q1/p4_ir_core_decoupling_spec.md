# P4 IR -> Core Decoupling - Detailed Specification

- Status: Implemented
- Version: 1.1
- Effective phase: P4 (`2026-03-16` -> `2026-03-29`)
- Hard deadline for exception removal: `2026-04-30`
- Scope: `policy-engine`
- Owners: `team-ir` (primary), `team-core`, `team-scientist`, `team-foundry`
- Related docs:
  - `p1_import_policy_v2_spec.md`
  - `p3_core_fabric_runtime_decoupling_spec.md`
  - `p1_refactor_queue.md`
  - `import_debt_register.csv`
  - `import_exceptions.toml`
  - `import_exceptions_registry.md`
  - `arch_cycles_register.csv`
  - `src/polisyos/ir/README.md`
  - `src/polisyos/core/contracts/README.md`

## 1. Context and Problem Statement

Current architecture debt cluster for this phase:

1. `Q5` in `p1_refactor_queue.md` is open:

   - eliminate `ir -> core` (`ARCH001-0001..0028`).
2. Active debt rows in `import_debt_register.csv`:

   - 28 `ARCH001` entries in 10 IR files (`connectors`, `fact_log`, `registry_fragments`, `linker`, `world/ids`, and 5 analytics modules).
3. Active temporary exceptions:

   - `E-2026-02-IR-CORE-001..010` (all expire on `2026-04-30`).
4. Import gate on `2026-02-09` reports no unmanaged violations, but still reports all `ir -> core` edges as `Allowed exceptions`.
5. Runtime package cycles on `2026-02-09` include:

   - `polisyos.core, polisyos.ir`
   - `polisyos.foundry, polisyos.foundry.domain`
     The `core <-> ir` cycle remains a direct blocker for DAG closure in this stream.

Net effect: IR layer still imports core canonicalization and core artifact/contracts helpers, violating target DAG and preventing closure of `Q5` and `CYCLE-001`.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Remove all production imports `polisyos.ir.* -> polisyos.core.*` in code under `src/polisyos/ir/**`.
2. Consolidate IR canonicalization + hashing usage to one public IR-owned API.
3. Remove direct `core.artifacts.*` and `core.contracts.*` dependencies from IR analytics persist/load functions.
4. Preserve persisted artifact semantics (`kind`, `media_type`, CAS determinism, schema naming) for existing pipelines.
5. Remove `E-2026-02-IR-CORE-001..010`, close `ARCH001-0001..0028`, and eliminate `core <-> ir` cycle evidence from import gate output.

### 2.2 Non-Goals (P4)

1. Full redesign of analytics report schemas (`UncertaintyEnvelope`, `HTEResult`, `CausalEffectReport`, etc.).
2. Replacement of `FileSystemCAS` storage engine or manifest format.
3. Changes to artifact naming conventions (`ir.*` kinds) or global migration of all core contracts.
4. Closure of `foundry <-> foundry.domain` cycle (handled in P5 stream).

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Dependency direction after P4

Required direction:

1. `ir` MUST depend only on `{ir, common}` for internal package imports.
2. `core`, `fabric`, `foundry`, `runtime`, `scientist`, `lex`, and `scholar` MAY depend on IR public contracts.
3. IR-internal persistence helpers MUST be expressed via IR-owned contracts/protocols, not core internals.

### 4.2 Canonical ownership

Canonical ownership after P4:

| Current owner/usage                                                                          | Canonical P4 owner                                                  |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `polisyos.core.canon.*` consumed by IR                                                       | `polisyos.ir.canon`                                                 |
| Analytics artifact refs in `core.contracts.{uncertainty,hte,causal,distributional,backtest}` | IR-owned refs (`polisyos.ir.refs`)                                  |
| IR analytics imports of `core.artifacts.manifest` and `core.artifacts.store`                 | IR-owned artifact I/O contract/protocol (`polisyos.ir.artifacts.*`) |

### 4.3 Compatibility contract (one release)

For one release window after P4 merge:

1. `core.contracts.{uncertainty,hte,causal,distributional,backtest}` SHOULD remain valid as thin facades/re-exports to IR-owned refs.
2. Existing import paths for `polisyos.core.canon` MAY remain available as compatibility surface, but IR code MUST NOT import them.
3. Compatibility modules MUST NOT contain duplicated business logic.

## 5. Detailed Technical Design

### 5.1 Canon/hash API consolidation

Required implementation:

1. Make `src/polisyos/ir/canon.py` the single IR canonicalization+hash API used by IR modules.
2. Ensure the API covers required operations currently consumed from core:

   - `CanonSpec`
   - `CanonViolation`
   - `to_canonical_bytes(...)`
   - `from_canonical_bytes(...)`
   - `content_hash(...)`
3. Rewire IR modules to import canon/hash only from `polisyos.ir.canon`:

   - `src/polisyos/ir/connectors.py`
   - `src/polisyos/ir/fact_log.py`
   - `src/polisyos/ir/registry_fragments.py`
   - `src/polisyos/ir/linker/_trinity_linker.py`
   - `src/polisyos/ir/world/ids.py`
   - `src/polisyos/ir/analytics/{uncertainty,hte,distributional,causal,backtest}.py`

Hard constraints:

1. Canonical JSON output MUST remain byte-identical for existing payload fixtures.
2. SHA256 digests and `sha256:<hex>` artifact IDs MUST remain stable for unchanged payloads.

### 5.2 IR analytics persistence boundary extraction

Current issue:

- IR analytics modules import `core.artifacts.manifest.SchemaInfo`, `core.artifacts.store.PutOptions`, and `core.contracts.*Ref` directly inside persist/load helpers.

Required implementation:

1. Introduce IR-owned artifact I/O contract surface (protocol + options models) under `src/polisyos/ir/artifacts/`.
2. Persist/load helpers in the 5 analytics modules MUST depend only on:

   - IR analytics models
   - IR canon API
   - IR artifact I/O protocol/contracts
   - IR reference types
3. Persist/load helper public function names and behavior MUST stay stable:

   - `persist_uncertainty_envelope` / `load_uncertainty_envelope`
   - `persist_hte_result` / `load_hte_result`
   - `persist_policy_recommendation` / `load_policy_recommendation`
   - `persist_distributional_report` / `load_distributional_report`
   - `persist_causal_effect_report` / `load_causal_effect_report`
   - `persist_backtest_report` / `load_backtest_report`
4. Returned ref objects MUST preserve current `kind` and `media_type` values.

### 5.3 IR-owned reference types and core facade alignment

Required implementation:

1. Define canonical analytics refs in IR (`src/polisyos/ir/refs.py` or equivalent IR contracts module):

   - `UncertaintyEnvelopeRef`
   - `HTEResultRef`
   - `PolicyRecommendationRef`
   - `CausalEffectReportRef`
   - `DistributionalReportRef`
   - `BacktestReportRef`
2. Convert core contract modules into thin compatibility facades:

   - `src/polisyos/core/contracts/uncertainty.py`
   - `src/polisyos/core/contracts/hte.py`
   - `src/polisyos/core/contracts/causal.py`
   - `src/polisyos/core/contracts/distributional.py`
   - `src/polisyos/core/contracts/backtest.py`
3. `src/polisyos/core/contracts/__init__.py` MUST keep the same exported names.

### 5.4 Regression prevention rules

1. `src/polisyos/ir/**` MUST NOT import `polisyos.core.*` (including function-local and lazy imports).
2. TYPE_CHECKING-only imports to `polisyos.core.*` in IR SHOULD be removed as part of this phase to avoid hidden boundary drift.
3. New reusable IR references/contracts MUST be added in IR first, not core.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-03-16` -> `2026-03-18`): establish IR canon/hash API and IR-owned artifact/ref contracts.
2. `M2` (`2026-03-18` -> `2026-03-22`): rewire non-analytics IR modules (`connectors`, `fact_log`, `registry_fragments`, `linker`, `world/ids`).
3. `M3` (`2026-03-22` -> `2026-03-26`): rewire 5 IR analytics modules and align core contract facades.
4. `M4` (`2026-03-27` -> `2026-03-29`): remove exceptions/debt rows, update cycle/debt docs, finalize freeze evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: IR canon/hash consolidation + IR ref/contracts foundation.
2. `PR-B`: Replace direct `core.canon` imports in non-analytics IR modules.
3. `PR-C`: Refactor IR analytics persist/load boundary and core contract facades.
4. `PR-D`: Governance cleanup (`exceptions`, `debt`, `queue`, `cycle register`) + full validation evidence.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `import_exceptions.toml`

   - remove `E-2026-02-IR-CORE-001..010`.
2. `import_exceptions_registry.md`

   - mark/remove the same IDs from active set.
3. `import_debt_register.csv`

   - remove/close `ARCH001-0001..0028`.
4. `p1_refactor_queue.md`

   - mark `Q5` as `Done` with closure date.
5. `arch_cycles_register.csv`

   - update `CYCLE-001` status based on post-P4 cycle output (close if absent).

### 7.2 Required verification commands

Architecture and freeze checks:

```bash
python3 tools/quality/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p4_metrics \
  --summary-path .tmp/p4_metrics/summary.json \
  --print-summary

python3 tools/quality/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p4_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p4_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Targeted tests:

```bash
python3 -m pytest \
  tests/unit/ir/test_uncertainty.py \
  tests/unit/ir/test_hte_backtest.py \
  tests/unit/ir/test_registry_fragments.py \
  tests/contract/test_trinity_linker_contract.py \
  tests/unit/scientist/test_propagate_uncertainty_node.py \
  tests/unit/scientist/test_decision_packet_node_v3.py \
  tests/unit/foundry/analysis/test_distributional.py
```

Recommended new tests for P4:

```bash
python3 -m pytest \
  tests/unit/ir/test_canon_hash_parity.py \
  tests/unit/ir/test_no_core_imports.py \
  tests/unit/core/contracts/test_ir_ref_facades.py
```

## 8. Acceptance Criteria and DoD

P4 is complete only if all criteria are met:

1. `src/polisyos/ir/**` has zero imports from `polisyos.core.*`.
2. `ARCH001-0001..0028` are absent from current import-gate output and debt register.
3. Exceptions `E-2026-02-IR-CORE-001..010` are removed from active set.
4. Runtime cycle output no longer contains `polisyos.core, polisyos.ir`.
5. Persist/load helpers for IR analytics preserve round-trip behavior and artifact metadata contract.
6. Compatibility imports from `polisyos.core.contracts.{uncertainty,hte,causal,distributional,backtest}` remain functional.
7. Blocking freeze comparison passes with no architecture regression.

## 9. Risks and Mitigations

| Risk                                                        | Impact | Mitigation                                                                  |
| ----------------------------------------------------------- | ------ | --------------------------------------------------------------------------- |
| Canon/hash drift after ownership move                       | High   | Golden vectors + parity tests for canonical bytes and digest outputs        |
| Runtime incompatibility with store protocol adapters        | High   | Integration tests using real `FileSystemCAS` via existing persist/load APIs |
| Consumer breakage from ref ownership inversion              | Medium | Keep core contract modules as thin facades for one release                  |
| Hidden IR->core coupling via local imports or TYPE_CHECKING | High   | Add explicit no-core-import test for `src/polisyos/ir/**`                   |
| Debt/docs drift from code closure                           | Medium | Treat registry/debt/queue/cycle updates as mandatory in closure PR          |

## 10. Post-P4 Follow-Ups (Out of Scope)

1. Decide long-term deprecation window for core facade modules that now re-export IR refs.
2. Evaluate moving shared canon/hash implementation to `common` if additional lower layers need the same owner-neutral API.
3. Continue cycle cleanup in P5 (`foundry <-> foundry.domain`) and plugin unification tracks.

## 11. Baseline Snapshot for P4 Planning (`2026-02-09`)

From `collect_arch_metrics.py` (`.tmp/p4_prep/summary.json`):

- `package_cycles_count = 2`
- `import_violations_count = 0` (with active temporary exceptions)
- `test_collect_errors_count = 42`
- `ruff_total_issues = 1216`
- `stale_sources_missing_paths_count = 40`

From `lint_imports.py` (`.tmp/p4_prep/import_gate.txt`):

- `Violations: none`
- Active allowed exceptions are exactly `E-2026-02-IR-CORE-001..010`.
- Runtime package cycles include `polisyos.core, polisyos.ir` and `polisyos.foundry, polisyos.foundry.domain`.

## 12. Implementation Evidence (`2026-02-09`)

### 12.1 Runtime and import-boundary outcomes

1. Eliminated all `src/polisyos/ir/** -> polisyos.core.*` imports:

   - rewired canon/hash usage in:
     - `src/polisyos/ir/connectors.py`
     - `src/polisyos/ir/fact_log.py`
     - `src/polisyos/ir/registry_fragments.py`
     - `src/polisyos/ir/linker/_trinity_linker.py`
     - `src/polisyos/ir/world/ids.py`
     - `src/polisyos/ir/analytics/{uncertainty,hte,distributional,causal,backtest}.py`
2. Extended IR canonical API in `src/polisyos/ir/canon.py`:

   - added `content_hash`, `from_canonical_obj`, `from_canonical_bytes`.
3. Added IR-owned artifact contract layer:

   - `src/polisyos/ir/artifacts/contracts.py`
   - `src/polisyos/ir/artifacts/io.py`
   - `src/polisyos/ir/artifacts/__init__.py`
4. Promoted analytics refs to canonical IR ownership in `src/polisyos/ir/refs.py`.
5. Converted core analytical contracts to thin compatibility facades:

   - `src/polisyos/core/contracts/backtest.py`
   - `src/polisyos/core/contracts/causal.py`
   - `src/polisyos/core/contracts/distributional.py`
   - `src/polisyos/core/contracts/hte.py`
   - `src/polisyos/core/contracts/uncertainty.py`

### 12.2 Debt and governance artifacts updated

1. Removed active exceptions `E-2026-02-IR-CORE-001..010`:

   - `import_exceptions.toml`
   - `import_exceptions_registry.md`
2. Removed debt rows `ARCH001-0001..0028`:

   - `import_debt_register.csv`
3. Updated queue status:

   - `p1_refactor_queue.md` (`Q5` -> `Done`, `2026-02-09`).
4. Updated cycle register:

   - `arch_cycles_register.csv` (`CYCLE-001` -> `closed`).

### 12.3 Documentation updates

1. `src/polisyos/ir/README.md` updated for IR-owned canon/artifact/ref dependency model.
2. `src/polisyos/core/contracts/README.md` updated to document analytical contract facades re-exported from IR.

### 12.4 Verification results

Architecture gate (`collect_arch_metrics.py`, `2026-02-09T21:14:31Z`):

- `package_cycles_count = 1` (was 2 before P4 prep; core/ir cycle removed)
- `import_violations_count = 0`
- `test_collect_errors_count = 42`

Import gate (`.tmp/p4_metrics/import_gate.txt`):

- `Violations: none`
- `Allowed exceptions: none`
- Remaining runtime cycle only: `polisyos.foundry <-> polisyos.foundry.domain`

Freeze comparison:

- `compare_baseline.py --mode blocking` -> `[OK] Architecture freeze checks passed.`

Targeted tests:

- `27 passed`:
  - `tests/unit/ir/test_uncertainty.py`
  - `tests/unit/ir/test_hte_backtest.py`
  - `tests/unit/ir/test_registry_fragments.py`
  - `tests/contract/test_trinity_linker_contract.py`
  - `tests/unit/foundry/analysis/test_distributional.py`
  - `tests/unit/scientist/test_decision_packet_node_v3.py`

New P4 tests:

- `6 passed`:
  - `tests/unit/ir/test_canon_hash_parity.py`
  - `tests/unit/ir/test_no_core_imports.py`
  - `tests/unit/core/contracts/test_ir_ref_facades.py`

Environment note:

- `tests/unit/scientist/test_propagate_uncertainty_node.py` could not be collected in this environment due missing optional dependency `jax`.
