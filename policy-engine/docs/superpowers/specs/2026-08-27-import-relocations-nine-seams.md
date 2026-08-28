# Import Relocations: Nine Rows — Execution Spec

## Authority and fixed base

This spec records the user-authorized relocation work from attached branch
`codex/import-relocations-nine-seams` at
`2525da7306d329ae28fa394690e1c39133eb0d55` on 2026-08-27.

The work is local only: no push, merge, or rebase. The two ARCH004 findings,
`runtime -> corpus`, and the observability family beyond the one shared
`simulation_proof_bridge` statement are out of scope.

## Invariants

- Classify all 39 target statements before the first source edit. Each
  classification names the bound symbols and is either `consumer-up`,
  `shared-contract-down`, or `ambiguous` with an exact coordinate.
- A facade re-spelling cannot legalize a denied direction. Every repair changes
  ownership or moves the executable consumer to its legal composition root.
- Prefer `wire-existing`, then `extend-existing`, then `consolidate-existing`,
  and only then add a module, package, export, constraint, or surface.
- The widening ledger starts at 0/10. A new module/package, a new
  authority-publishing export, a loosened architecture constraint, or a new
  surface consumes a round. Moving a symbol downward into an existing allowed
  root is round-free. A withdrawn round does not count.
- One commit per declared seam. At every boundary, read back branch attachment,
  compare the declared and observed path sets, and record the widening ledger.
- Use focused behavioral tests, changed-file Ruff, recomputing validators, and
  the nine literal row-closure commands. Do not run full pytest.
- Read direct exit codes before processing output. Measured validators record
  `user + sys` and an `uptime` pair. Set-level counts require two independent
  derivations; disagreement remains visible.
- `guardrails sync` is permitted only with
  `--skip-deep-import-baseline`. The deep-import baseline is edited surgically
  from a complete enumeration, with additions and removals listed separately
  and one citation for every added edge.

## Ownership design

### Lex/Foundry intervention seam

Keep legal compilation and neutral intervention declarations in Lex/IR. Move
temporal estimator execution to its existing upper Scientist causal node and
hierarchical search execution to the existing Scientist policy-search owner.
Lower the dependency-neutral compiled-intervention artifact to IR and make both
Lex and Foundry consume the same identity. Treat all eight directions as one
atomic seam so neither half recreates the bidirectional coupling.

### Core CLI seams

Core retains generic parser and low-level commands. Metric validation and the
three Scientist evaluation commands move to a composition root that is already
allowed to depend on Scientist; the public `polisyos` entry point delegates to
that composition owner. Dynamic import or facade indirection is not a repair.

### Foundry/Scientist seams

- Scientist owns release postflight admission. The D5 request remains
  non-authoritative until a real Scientist consumer verifies the content-bound
  handoff and persists the scoped decision.
- Calibration meta-policy and judge-threshold policy execute in Scientist;
  Foundry supplies measurements and calibration inputs.
- Failure-card DTOs lower to the existing neutral IR analytics contract;
  Foundry and Scientist share that identity.
- Generic embedders lower to a Foundry implementation owner; Scientist may
  re-export the identical implementation for compatibility, but no duplicate
  contract or algorithm remains.

### IR seams

- IR retains serializable manifests, declarations, and pure codecs. Foundry
  materializes method-specific protocol DTOs and execution strategies.
- Scientist owns executable backtest plans, ontology service calls, latent
  governance decisions, and their orchestration adapters. IR accepts frozen
  neutral inputs/snapshots and persists neutral artifacts.
- Shared `ComputeBudget` and truthfulness identities lower to IR. Existing
  upper modules re-export the same identities rather than carrying copies.
- `ABMResult` becomes an independent IR analytical result; conversion to Core
  execution contracts belongs in Foundry's existing simulation boundary.
- `ir/observation/compiler.py` is one physical move with two separately closed
  predicates: Foundry calibration ownership and the external JAX dependency.

## Collision rulings

`ir/analytics/simulation_proof_bridge.py` stays in IR. Its proof, evidence, and
calibration artifacts are legitimately IR-owned; the inversion is the duplicate
truthfulness identity. The complete truthfulness model/helper surface is
consolidated in existing `ir/analytics/_truthfulness.py`, and Core re-exports
those exact identities. The separate observability lane inherits that lower
owner and remains responsible for its other family members.

`ir/observation/compiler.py` moves its tensor materialization and calibration
bundle compiler together to Foundry. The final journal and closures must still
name `ir -> jax` and `ir -> foundry` independently.

## Pattern pass and capability bar

- P01/P02/P12: no contract-only relocation; every moved producer has a bridge
  and a real consumer, or the residual capability label remains explicit.
- P05/P15/P32/P37: producer statements and LLM/candidate output never establish
  an authority-grade gate. Admission resolves, content-binds, and verifies.
- P06/P27/P31: consolidate canonical identities and fix each inversion class,
  not one spelling.
- P29/P33/P38: tests execute the real boundary and include a divergent negative
  case; import strings and success exit codes are not the property.
- P35/P36: all counts come from complete denominators and authoritative claims
  cite their finding IDs or exact source coordinates.
- P39: this spec, the implementation plan, execution journal, baseline record,
  and tests are mandatory companions and do not count as mechanism paths.
- P40/P41: bucket repeated findings and establish whose red each gate is from
  the pinned slice base before excluding it.

Capability completion is assessed as contract + producer + persisted
artifact/event + orchestration bridge + consumer + verification + external or
audit/API/dashboard surface (or explicit `surface_out_of_scope`) + negative
semantic test. Anything short is labeled precisely in the execution journal.
