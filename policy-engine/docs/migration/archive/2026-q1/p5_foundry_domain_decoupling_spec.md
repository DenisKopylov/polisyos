# P5 Foundry <-> Foundry.Domain Decoupling - Detailed Specification

- Status: Implemented
- Version: 1.0
- Effective phase: P5 (`2026-03-30` -> `2026-04-12`)
- Hard deadline for cycle closure: `2026-04-12`
- Scope: `policy-engine`
- Owners: `team-foundry` (primary), `team-core`, `team-scientist`
- Related docs:
  - `p1_import_policy_v2_spec.md`
  - `p1_refactor_queue.md`
  - `p4_ir_core_decoupling_spec.md`
  - `arch_cycles_register.csv`
  - `src/polisyos/foundry/README.md`
  - `tools/lint/lint_imports.py`

## 1. Context and Problem Statement

Planning baseline for this phase (before implementation):

1. `Q1` in `p1_refactor_queue.md` was open:
   - break cycle `CYCLE-002` (`polisyos.foundry <-> polisyos.foundry.domain`).
2. `arch_cycles_register.csv` marked `CYCLE-002` as `open` with `critical` severity.
3. Fresh architecture snapshot on `2026-02-09` reports:
   - `package_cycles_count = 1`
   - only remaining cycle: `polisyos.foundry, polisyos.foundry.domain`
4. Import gate reports no `ARCH` violations, meaning this is pure package-cycle debt, not a policy matrix violation.
5. The cycle is structural: execution layer imports domain models, and domain mechanisms import execution base classes.

Current cross-package runtime edges driving the cycle:

| Direction | File | Import |
| --- | --- | --- |
| `foundry -> foundry.domain` | `src/polisyos/foundry/base.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/agents.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/_executor_snapshots.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/calibration/pure_executor.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/calibration/calibrator.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/loss.py` | `from polisyos.foundry.domain.state import GlobalState` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/registry.py` | `from polisyos.foundry.domain.mechanisms import ...` |
| `foundry -> foundry.domain` | `src/polisyos/foundry/compile/trinity_compiler.py` | `from polisyos.foundry.domain.mechanisms import build_treasury_plan` |
| `foundry.domain -> foundry` | `src/polisyos/foundry/domain/mechanisms/fiscal.py` | `from polisyos.foundry.base import Mechanism, PatchMap` |
| `foundry.domain -> foundry` | `src/polisyos/foundry/domain/mechanisms/labor.py` | `from polisyos.foundry.base import ComplexMechanism, PatchMap` |
| `foundry.domain -> foundry` | `src/polisyos/foundry/domain/mechanisms/fiscal.py` | `from polisyos.foundry.types import FidelityLevel` |
| `foundry.domain -> foundry` | `src/polisyos/foundry/domain/mechanisms/labor.py` | `from polisyos.foundry.types import FidelityLevel` |

Net effect: the last package cycle blocks full DAG closure promised by P0-P4 and keeps `team-foundry` debt item unresolved.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Eliminate runtime cycle `polisyos.foundry <-> polisyos.foundry.domain`.
2. Extract state and mechanism protocol contracts into a dedicated contract layer.
3. Separate compute mechanisms from domain-model package.
4. Keep existing external import paths functional for one release via compatibility facades.
5. Close governance items `Q1` and `CYCLE-002` with reproducible evidence.

### 2.2 Non-Goals (P5)

1. Plugin discovery unification (`P6` stream).
2. Full redesign of `GlobalState` semantics or economic model equations.
3. Rewrite of Foundry compile/execute artifact schemas (`ProgramGraph`, `ExecPlan`, `SimulationResult`).
4. Removal of all compatibility shims in the same phase (scheduled as follow-up).

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Canonical module boundaries after P5

P5 introduces canonical ownership split:

1. `src/polisyos/foundry/contracts/*`
   - canonical state and protocol contracts.
2. `src/polisyos/foundry/mechanisms/*`
   - canonical compute mechanism implementations.
3. `src/polisyos/foundry/domain/*`
   - compatibility facade layer only (no canonical compute ownership).

### 4.2 Canonical ownership mapping

| Current module | Canonical P5 owner | Compatibility behavior |
| --- | --- | --- |
| `src/polisyos/foundry/domain/state.py` | `src/polisyos/foundry/contracts/state.py` | domain module re-exports canonical symbols |
| `src/polisyos/foundry/base.py` | `src/polisyos/foundry/contracts/mechanism.py` | base module becomes thin facade |
| `src/polisyos/foundry/types.py` | `src/polisyos/foundry/contracts/fidelity.py` | types module re-exports enum |
| `src/polisyos/foundry/domain/mechanisms/fiscal.py` | `src/polisyos/foundry/mechanisms/fiscal.py` | domain path re-exports with deprecation warning |
| `src/polisyos/foundry/domain/mechanisms/labor.py` | `src/polisyos/foundry/mechanisms/labor.py` | domain path re-exports with deprecation warning |
| `src/polisyos/foundry/domain/mechanisms/treasury.py` | `src/polisyos/foundry/mechanisms/treasury.py` | domain path re-exports with deprecation warning |

### 4.3 Dependency direction invariants

After P5 merge:

1. Files under `src/polisyos/foundry/**` outside `src/polisyos/foundry/domain/**` MUST NOT import `polisyos.foundry.domain.*`.
2. Canonical state typing in Foundry runtime/compile/calibration code MUST come from `polisyos.foundry.contracts.state`.
3. Mechanism protocol types (`Mechanism`, `ComplexMechanism`, `PatchMap`, `FidelityLevel`) MUST come from `polisyos.foundry.contracts.*`.
4. `registry.py` and `compile/trinity_compiler.py` MUST import canonical mechanism implementations from `polisyos.foundry.mechanisms.*`.
5. `src/polisyos/foundry/domain/**` MAY import canonical modules for compatibility, but MUST NOT host new business logic.

### 4.4 One-release compatibility contract

For one release after P5:

1. Legacy imports remain valid:
   - `polisyos.foundry.domain.state.*`
   - `polisyos.foundry.domain.mechanisms.*`
   - `polisyos.foundry.base.*`
   - `polisyos.foundry.types.FidelityLevel`
2. Compatibility modules SHOULD emit `DeprecationWarning` with target import path.
3. Compatibility modules MUST NOT duplicate core logic; they only re-export canonical implementations.

## 5. Detailed Technical Design

### 5.1 Contract extraction (`foundry/contracts`)

Required additions:

1. `src/polisyos/foundry/contracts/state.py`
   - move `AgentState`, `FirmState`, `MarketState`, `GlobalState`, and `GlobalState.empty`.
2. `src/polisyos/foundry/contracts/fidelity.py`
   - canonical `FidelityLevel` enum.
3. `src/polisyos/foundry/contracts/mechanism.py`
   - canonical `PatchRecord`, `PatchMap`, `Mechanism`, `ComplexMechanism`.
4. `src/polisyos/foundry/contracts/__init__.py`
   - curated export surface for external and internal consumers.

Hard constraints:

1. Dataclass field names and dtypes in `GlobalState` MUST stay unchanged.
2. Existing behavior of `GlobalState.empty(n_agents, n_firms)` MUST remain byte-compatible for current tests.
3. `FidelityLevel` wire values (`"fluid"`, `"relaxed"`, `"hard"`) MUST remain unchanged.

### 5.2 Compute mechanism separation (`foundry/mechanisms`)

Required changes:

1. Create canonical mechanism modules:
   - `src/polisyos/foundry/mechanisms/fiscal.py`
   - `src/polisyos/foundry/mechanisms/labor.py`
   - `src/polisyos/foundry/mechanisms/treasury.py`
   - `src/polisyos/foundry/mechanisms/__init__.py`
2. Rewire mechanism imports:
   - `src/polisyos/foundry/registry.py`
   - `src/polisyos/foundry/compile/trinity_compiler.py`
3. Convert domain mechanism modules into compatibility facades pointing to canonical modules.

Hard constraints:

1. Mechanism class names and constructor signatures MUST stay backward-compatible.
2. `build_treasury_plan()` deterministic hash behavior MUST stay unchanged.

### 5.3 Foundry internal rewiring to canonical contracts

Mandatory rewiring:

1. Replace `polisyos.foundry.domain.state` imports with `polisyos.foundry.contracts.state` in:
   - `src/polisyos/foundry/base.py`
   - `src/polisyos/foundry/agents.py`
   - `src/polisyos/foundry/_executor_snapshots.py`
   - `src/polisyos/foundry/calibration/pure_executor.py`
   - `src/polisyos/foundry/calibration/calibrator.py`
   - `src/polisyos/foundry/loss.py`
2. Replace `polisyos.foundry.types` imports with `polisyos.foundry.contracts.fidelity` in canonical implementations.
3. Keep `src/polisyos/foundry/base.py` and `src/polisyos/foundry/types.py` as compatibility facades for one release.

### 5.4 Regression prevention and import-boundary tests

Required new tests:

1. `tests/foundry/test_no_foundry_domain_imports.py`
   - AST scan: forbid `polisyos.foundry.domain.*` imports in `src/polisyos/foundry/**` excluding `src/polisyos/foundry/domain/**`.
2. `tests/foundry/test_domain_compat_facades.py`
   - verify legacy imports resolve and point to canonical implementations.
3. `tests/foundry/test_contract_state_compat.py`
   - verify `GlobalState.empty()` parity and key dataclass behavior across old and new import paths.

### 5.5 Documentation updates

Required docs sync:

1. `src/polisyos/foundry/README.md`
   - update package map to show `contracts/` and `mechanisms/` canonical ownership.
2. `src/polisyos/foundry/calibration/README.md`
   - update state import references to canonical contracts path.
3. `tools/README.md` (Foundry examples section)
   - update references from `foundry.domain` to canonical modules.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-03-30` -> `2026-04-01`): introduce `foundry/contracts` and compatibility shims.
2. `M2` (`2026-04-01` -> `2026-04-05`): move built-in mechanisms to `foundry/mechanisms`, rewire `registry` and compiler.
3. `M3` (`2026-04-06` -> `2026-04-09`): remove all non-domain `foundry -> foundry.domain` imports and add boundary tests.
4. `M4` (`2026-04-10` -> `2026-04-12`): governance closure (`Q1`, `CYCLE-002`), docs refresh, freeze evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: `foundry/contracts` extraction + compatibility facades (`base`, `types`, `domain/state`).
2. `PR-B`: canonical `foundry/mechanisms` + registry/compiler rewiring.
3. `PR-C`: internal import rewiring (`agents`, `loss`, `snapshots`, calibration modules) + new tests.
4. `PR-D`: governance/docs closure and full architecture validation evidence.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `arch_cycles_register.csv`
   - mark `CYCLE-002` as `closed` with closure date and evidence note.
2. `p1_refactor_queue.md`
   - mark `Q1` as `Done` with closure date.
3. `import_debt_register.csv`
   - if P5-specific debt IDs are introduced during implementation, they MUST be removed/closed by phase end.
4. `import_exceptions.toml` and `import_exceptions_registry.md`
   - P5 SHOULD complete without new exceptions; if temporary exceptions are added, they MUST include owner/expiry and be tracked.

### 7.2 Required verification commands

Architecture and freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p5_metrics \
  --summary-path .tmp/p5_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p5_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p5_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Targeted regression tests:

```bash
python3 -m pytest \
  tests/foundry/test_global_state.py \
  tests/foundry/test_fiscal.py \
  tests/foundry/test_patch_executor.py \
  tests/foundry/test_execute_facade_smoke.py \
  tests/foundry/test_calibrator_mvp.py \
  tests/scientist/test_compiler.py
```

Recommended new P5 tests:

```bash
python3 -m pytest \
  tests/foundry/test_no_foundry_domain_imports.py \
  tests/foundry/test_domain_compat_facades.py \
  tests/foundry/test_contract_state_compat.py
```

## 8. Acceptance Criteria and DoD

P5 is complete only if all criteria are met:

1. Import gate cycle output has no `polisyos.foundry, polisyos.foundry.domain` cycle.
2. `src/polisyos/foundry/**` outside `domain/**` has zero imports from `polisyos.foundry.domain.*`.
3. Canonical ownership exists and is used:
   - state/protocol in `foundry/contracts`
   - built-in mechanisms in `foundry/mechanisms`
4. Legacy imports from `foundry.domain.*`, `foundry.base`, and `foundry.types` remain functional through facades.
5. `Q1` and `CYCLE-002` are marked closed in governance artifacts.
6. Blocking freeze check passes with no architecture regressions.

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Import-path breakage for downstream users/tests | High | Keep one-release compatibility facades and add explicit compatibility tests |
| Behavior drift after module move | High | Golden tests for `GlobalState.empty` and mechanism output parity |
| Hidden reintroduction of `foundry -> domain` imports | High | Add AST boundary test and keep it in default CI test suite |
| Scope creep into plugin/runtime redesign | Medium | Keep P5 strictly limited to cycle closure and contract extraction |
| Documentation drift | Medium | Treat README updates as required in closure PR |

## 10. Post-P5 Follow-Ups (Out of Scope)

1. Remove compatibility facades after one-release deprecation window (target: `2026-06-30`).
2. Align mechanism discovery with P6 unified component model.
3. Evaluate moving Foundry contracts to `core.contracts` only if cross-layer reuse justifies it.

## 11. Baseline Snapshot for P5 Planning (`2026-02-09`)

Snapshot evidence used by this specification:

- `package_cycles_count = 1`
- `import_violations_count = 0`
- `test_collect_errors_count = 42`
- remaining cycle: `polisyos.foundry <-> polisyos.foundry.domain`

This confirms P5 is the final architecture cycle closure step after P4 completion.

## 12. Implementation Evidence (`2026-02-09`)

### 12.1 Canonical ownership implemented

1. Added canonical state/protocol contracts:
   - `src/polisyos/foundry/contracts/state.py`
   - `src/polisyos/foundry/contracts/fidelity.py`
   - `src/polisyos/foundry/contracts/mechanism.py`
   - `src/polisyos/foundry/contracts/__init__.py`
2. Added canonical mechanism implementations:
   - `src/polisyos/foundry/mechanisms/fiscal.py`
   - `src/polisyos/foundry/mechanisms/labor.py`
   - `src/polisyos/foundry/mechanisms/treasury.py`
   - `src/polisyos/foundry/mechanisms/__init__.py`
3. Converted legacy modules to compatibility facades:
   - `src/polisyos/foundry/base.py`
   - `src/polisyos/foundry/types.py`
   - `src/polisyos/foundry/domain/state.py`
   - `src/polisyos/foundry/domain/mechanisms/{__init__,fiscal,labor,treasury}.py`

### 12.2 Runtime import rewiring completed

1. Rewired runtime/compile/calibration code to canonical contracts:
   - `src/polisyos/foundry/agents.py`
   - `src/polisyos/foundry/queue.py`
   - `src/polisyos/foundry/_executor_snapshots.py`
   - `src/polisyos/foundry/calibration/pure_executor.py`
   - `src/polisyos/foundry/calibration/calibrator.py`
   - `src/polisyos/foundry/loss.py`
2. Rewired mechanism consumers to canonical mechanisms:
   - `src/polisyos/foundry/registry.py`
   - `src/polisyos/foundry/compile/trinity_compiler.py`
3. Replaced `foundry.types` usage in Foundry source tree with `foundry.contracts.fidelity`.

### 12.3 Regression guards and docs

1. Added boundary/compatibility tests:
   - `tests/foundry/test_no_foundry_domain_imports.py`
   - `tests/foundry/test_domain_compat_facades.py`
   - `tests/foundry/test_contract_state_compat.py`
2. Updated docs:
   - `src/polisyos/foundry/README.md`
   - `src/polisyos/foundry/calibration/README.md`
   - `tools/README.md`

### 12.4 Governance closure artifacts

1. Closed cycle item:
   - `arch_cycles_register.csv` (`CYCLE-002` -> `closed`, closure note added).
2. Closed queue item:
   - `p1_refactor_queue.md` (`Q1` -> `Done` on `2026-02-09`).

### 12.5 Verification results

1. `lint_imports.py --fail-on-cycles`:
   - `Violations: none`
   - `Allowed exceptions: none`
   - `Cycles (runtime imports, package-level): none`
2. `collect_arch_metrics.py` (`.tmp/p5_metrics/summary.json`):
   - `package_cycles_count=0`
   - `import_violations_count=0`
   - `test_collect_errors_count=42`
3. `compare_baseline.py --mode blocking`:
   - `[OK] Architecture freeze checks passed.`
4. New P5 tests:
   - `tests/foundry/test_no_foundry_domain_imports.py`: passed
   - `tests/foundry/test_domain_compat_facades.py`: skipped in current env (`jax` missing)
   - `tests/foundry/test_contract_state_compat.py`: skipped in current env (`jax` missing)
