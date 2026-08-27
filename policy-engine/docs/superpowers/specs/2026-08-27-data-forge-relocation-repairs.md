# DataForge Relocation Repairs — Approved Execution Spec

## Authority

This spec records the architect-approved continuation for branch
`codex/import-relocate-data-forge` at `9300a06e9` on 2026-08-27. It is the
durable source for the implementation plan and execution ledger.

## Invariants

- Local Git only: no push, merge, or rebase.
- Never run `guardrails sync`.
- Targeted tests only; no full pytest run.
- Read command exit codes before any pipe.
- Record `user + sys` time with an `uptime` pair for measured validators.
- Derive every set-level count twice and report disagreement rather than
  normalizing it away.
- Continue the widening ledger from 4 with a hard ceiling of 8. Repairs inside
  rounds 1–4 consume no new round unless implementation proves they require a
  new authority-bearing seam. Repairs outrank rows 3–8.

## Required Repairs

### Immutable Ukraine receipts

The Ukraine read boundary must read manifest/output bytes once, verify those
bytes, and persist the same bytes in `FileSystemCAS`. Foundry and Scientist
must parse only the immutable CAS snapshots. Re-hashing or reopening producer
paths is not an acceptable repair.

### D4 authority

- The DataForge D4 request is routing-only. Producer-authored thresholds,
  waivers, resolved flags, or evidence grades cannot affect signoff.
- Scientist owns the versioned threshold and applies no producer waiver.
- Identity coverage is recomputed from raw identities against immutable
  registry evidence.
- Household observations remain exploratory and bounds-only. Coverage and
  validated/point-identified grades remain unestablished, so exact signoff is
  blocked.
- A falsifier must hold the receipt/hash witness constant while flipping a
  producer waiver; the authority result must remain rejected or unchanged.

### Foundry method input orchestration

- Persist all 13 validated method DTOs as lineage-bound CAS artifacts and one
  typed bundle.
- A selected route requires explicit `{contract_key, method_fqn}` with no
  default, validates contract compatibility, and invokes the existing method
  backend.
- Execution evidence cannot establish method validity or governance
  admissibility; presenting it as such must be rejected by a behavioral test.
- `d2_panel_observational` is the exercised workflow consumer. The other 12
  contracts are registered individually as selectable-but-unselected with an
  explicit capability state.

### Shared legal contracts

- Amend frozen row 21 to keep `latest_object_by_subject` in `common`; the
  complete consumer set already reaches that lowest root legally. Change no
  production code for this symbol.
- Remove the two package-gate Lex compatibility edges without loosening either
  architecture policy.

## Remaining Relocation Rows and Ledger

- Round 5: row 3, Scientist claim-adjudication decision bridge.
- Round 6: rows 4–6, Lex NormPack/transport benchmark consumer.
- Round 7: row 7, Scientist retrieval benchmark, diagnostic-only.
- Round 8: row 8, Lex-owned interactive search command.

If a repair consumes a round, take it and stop at round 8 with remaining rows
classified. Do not thin a repair to preserve a relocation row.

## Baseline and Governance Records

- Recompute deep-import edges with the canonical collector and an independent
  AST implementation after source freeze.
- Manually edit `architecture/baselines/imports/deep_import.json`, enumerating
  additions and removals separately. Every addition records its originating
  relocation statement or previously spent round. Cite each of the three
  Scientist Round-3 edges individually.
- Register the enforced-predicate conflict in which ARCH004 calls
  `polisyos.fabric.world` the facade while the deep-import guardrail treats it
  as unsupported. The witness is
  `runtime.quality.data_state_substrate -> fabric.world`, created by the
  architect's Phase-0 re-spelling instruction.
- Record the inherited Ruff diagnostics using the architect's same-binary,
  dual-tree comparison.
- Every new register row must name a closure signal that has been executed
  before the row is written.

## Final Predicates

Report separately:

1. source import linter;
2. release architecture guardrail, required to exit 0 with zero creep;
3. package-import gate, expected to remain independently red until its own
   unrelated debts close.

Reference bases: `238ea72fe` = exit 1 / 88, exit 0 / zero creep, exit 1 / 143.
Continuation head `9300a06e9` = exit 1 / 48, exit 1 / 22 creep, exit 1 / 150.
