# Import Relocations: Nine Rows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`
> task by task, and use `superpowers:verification-before-completion` before any
> completion claim.

**Goal:** Remove the 39 classified import inversions without loosening an
architecture constraint, restore the release guardrail through an enumerated
deep-import baseline transaction, and leave every target row's literal closure
command green.

**Spec:**
`docs/superpowers/specs/2026-08-27-import-relocations-nine-seams.md`

## Global procedure

- [x] Create an attached isolated worktree at the exact pinned base.
- [x] Reproduce the three baseline predicates and derive the target set twice.
- [x] Classify all 39 statements before source work; record 0 ambiguous.
- [ ] Execute the seams below serially, with one commit per seam.
- [ ] Freeze source, enumerate deep-import additions/removals twice, patch the
  baseline surgically, and run sync only with `--skip-deep-import-baseline`.
- [ ] Run focused closeout, every literal row command, and all three final
  predicates against the handed-back tree.

At every seam boundary:

1. run `git rev-parse --show-prefix`, `git status -sb`, and
   `git symbolic-ref -q HEAD`;
2. run focused pre-change characterization or RED falsifier;
3. implement the smallest legal owner move;
4. run focused GREEN tests, changed-file Ruff, and the seam's literal closure;
5. compare declared paths with `git diff --name-only`;
6. update the journal ledger, commit, and read attachment/commit back.

## Ordered seams

### Seam 1: Lex/Foundry intervention coupling — 8 statements

- [x] Lower the neutral compiled-intervention artifact to existing IR.
- [x] Move temporal DTR execution/materialization above Lex while leaving legal
  sequencing declarations and compilation in Lex/IR.
- [x] Move hierarchical policy-search execution to Scientist.
- [x] Update Foundry wiring, Scientist nodes, exports, docs, and focused tests
  as one atomic seam.
- [x] Close `lex -> foundry`, `lex -> scientist`, and `foundry -> lex`.

### Seam 2: Core metric-validation CLI — 1 statement

- [x] Move the metric-validation handler to the legal composition owner.
- [x] Preserve parser, exit-code, and JSON behavior through the supported CLI.
- [x] Close its contribution to `core -> scientist`.

### Seam 3: Core Scientist CLI — 3 statements

- [x] Move Gonka smoke, starter eval, and reflexion replay handlers to the same
  legal composition owner.
- [x] Preserve command names and public entry-point behavior without dynamic
  import indirection.
- [x] Close `core -> scientist`.

### Seam 4: D5 release acceptance — 1 statement

- [x] Establish Scientist as the real postflight consumer of the content-bound
  D5 request; keep Foundry compilation/execution below it.
- [x] Persist the scoped admission result and add a negative producer-authority
  test.
- [x] Close this `foundry -> scientist` statement first.

### Seam 5: Calibration policy pair — 2 statements

- [x] Move calibration meta-override application and judge-threshold registry
  use into existing Scientist owners; Foundry passes neutral inputs/results.
- [x] Preserve numerical calibration behavior and refusal-to-loosen semantics.

### Seam 6: Composition failure-card contract — 1 statement

- [x] Lower the DTO/enums to the existing IR analytics contract and make both
  Foundry and Scientist consume the same identity.
- [x] Prove producer, persisted artifact, and Scientist consumer round-trip.

### Seam 7: Policy-frontier embedders — 1 statement

- [x] Relocate the generic TF-IDF and optional sentence-transformer
  implementation to Foundry's existing method/backend ownership.
- [x] Preserve optional-dependency failure and Scientist compatibility through
  identity re-export only if the public contract is already published.

### Seam 8: IR method-protocol binding — 7 statements

- [x] Keep IR manifests and pure codecs; move concrete causal, econometric,
  microsimulation, ML, and network DTO materializers to Foundry data-plane.
- [x] Make `TemporalDTRTask` carry a neutral payload and validate/materialize it
  at the upper adapter.
- [x] Preserve deterministic round trips and one real downstream consumer.

### Seam 9: IR strategic/transportability adapters — 3 statements

- [x] Move Foundry solve-result interpretation and strategic response assembly
  to the existing Foundry strategic owner.
- [x] Move `SourceDomainSpec -> SourceDomain` conversion beside the Foundry ID
  engine; keep the neutral spec in IR.

### Seam 10: IR kernel lowering — 2 statements

- [ ] Remove the duplicate execution-aware IR lowering path and consolidate on
  the existing Foundry estimand compiler/kernel lowering implementation.
- [ ] Prove compile/execute/audit behavior and negative dispositions.

### Seam 11: IR calibration/JAX — 2 statements, two predicates

- [ ] Move the calibration target compiler, placebo materialization, and
  JAX/NumPy tensor work to existing Foundry calibration ownership.
- [ ] Retain neutral split/window/negative-control declarations in IR.
- [ ] Close `ir -> foundry` and `ir -> jax` separately.

### Seam 12: IR backtesting — 3 statements

- [ ] Store neutral plan payloads in IR and materialize/validate executable
  `HistoricalValidationPlan` instances in Scientist.
- [ ] Add malformed-payload rejection at Scientist intake and preserve matrix
  governance consumers.

### Seam 13: IR alignment governance — 2 statements

- [ ] Have Scientist compute ontology warnings and latent-governance snapshots;
  inject those frozen values into pure IR certificate construction/persistence.
- [ ] Prove service failure degrades or blocks according to the status contract.

### Seam 14: IR strategic budget identity — 1 statement

- [ ] Lower the dependency-free `ComputeBudget` contract to an existing IR
  module and re-export the identical type from Scientist.
- [ ] Add identity and round-trip assertions.

### Seam 15: IR phase-4 dynamics — 1 statement

- [ ] Make `ABMResult` an independent IR analytical DTO.
- [ ] Move Core execution-ref/result conversion to the existing Foundry
  simulation owner and reject malformed conversions.

### Seam 16: IR truthfulness identity — 1 statement

- [ ] Consolidate the complete model/parser/validation/extraction helper surface
  in existing IR truthfulness ownership.
- [ ] Make Core re-export exact identities, keep the simulation proof bridge in
  IR, and prove authority-negative behavior plus schema identity.

## Source freeze and closeout

- [ ] Re-run the source linter and independently derive every target pair.
- [ ] Enumerate the complete deep-import edge set twice. Write separate
  addition/removal lists and one citation per added edge.
- [ ] Patch `architecture/baselines/imports/deep_import.json` with
  `apply_patch`, not a formatter or sync.
- [ ] Run guardrail sync only as
  `uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline`.
- [ ] Run changed-file Ruff, focused seam/importer tests, recomputing validators,
  architecture guardrails, and all nine literal row commands.
- [ ] Re-run the source, release-guardrail, and package predicates with direct
  exit status, timing, uptime, and independent counts.
