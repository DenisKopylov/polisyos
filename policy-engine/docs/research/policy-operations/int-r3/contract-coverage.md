---
task_id: INT-R3
stage: 1
artifact_role: contract_coverage
status: amended
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - int_r3_delivery_coverage
may_not_use_for:
  - substantive_finding_substitute
---

# INT-R3 contract coverage

## Unified Deliverable Form

| Required section | Committed location |
| --- | --- |
| 1. Task And Project Fit | main deliverable §1 |
| 2. Current Repo Baseline | main §2, `repo-baseline.md`, amended by `repository-baseline-amendment.md` |
| 3. External Research Baseline | main §3, `external-evidence-ledger.md`, traced by `external-source-ledger.md` |
| 4. Result | main §4 and `benchmark-specification.md`, amended by `amendment-specification.md` |
| 5. Counterexamples And Failure Modes | main §5 |
| 6. Benchmark Or Fixture Proposal | main §6 and benchmark §§5–9, amended item-flow/coverage clauses |
| 7. Artifact Contract Sketch | main §7 |
| 8. Later Integration Handoff | main §8, amended stale DS6 allocation and principal route |
| 9. Promotion And Kill Rules | main §9, amended coverage and claim-use rules |
| 10. Open Questions For Consolidation | main §10 |

## Operational closure addendum

| Required item | Committed location |
| --- | --- |
| boundary census | main addendum §A1, baseline and baseline amendment |
| real operator workflow | main addendum §A2 |
| state machine | main addendum §A3 plus amended item-flow state |
| typed artifacts | main §7 and addendum §A4 |
| edge-case fixtures | main addendum §A5 plus narrowed `AUI-R06` controls |
| tabletop / fault injection | main addendum §A6 |
| capstone linkage | main addendum §A7 |

## Stage-3 amendment contract

| Requirement | Coverage |
| --- | --- |
| one row per audit finding | `amendment-ledger.md`, 17 package + 6 orientation |
| dispositions use registered vocabulary | `accepted`, `accepted_with_variation`, `declined_with_reason` only |
| dispositions reconcile to audit total | 18 + 5 + 0 = 23 |
| correct two false source anchors | `repository-baseline-amendment.md` |
| stop claiming sampled repository zeroes | baseline amendment search-scope and negative-claim tables |
| durable external traceability | `external-source-ledger.md` |
| resolving evidence for four novel constructs | `amendment-specification.md` §6 |
| bound contestable/invalid absorption | amendment specification §5 |
| programme feasibility split | amendment specification §2 |
| partition red-first battery | amendment specification §4 |
| narrow stale predicate | amendment specification §4, `AUI-R06` |
| split DS12 gate from comprehension use | amendment specification §1 |
| pre-terminal blocker observation | amendment specification §8 |
| classify DS6 allocation stale without appointment | amendment specification §3 and baseline amendment |
| preserve five commendations | amendment ledger `C001`–`C005` |
| preserve no-human-result negative | amendment specification §10 |

## Effective Markdown file set

```text
policy-engine/docs/research/policy-operations/int-r3-authority-ui-comprehension-benchmark.md
policy-engine/docs/research/policy-operations/int-r3/README.md
policy-engine/docs/research/policy-operations/int-r3/repo-baseline.md
policy-engine/docs/research/policy-operations/int-r3/external-evidence-ledger.md
policy-engine/docs/research/policy-operations/int-r3/benchmark-specification.md
policy-engine/docs/research/policy-operations/int-r3/finding-register.md
policy-engine/docs/research/policy-operations/int-r3/pattern-pass.md
policy-engine/docs/research/policy-operations/int-r3/contract-coverage.md
policy-engine/docs/research/policy-operations/int-r3/amendment-ledger.md
policy-engine/docs/research/policy-operations/int-r3/amendment-specification.md
policy-engine/docs/research/policy-operations/int-r3/repository-baseline-amendment.md
policy-engine/docs/research/policy-operations/int-r3/external-source-ledger.md
```

## Prohibited changes

This amendment does not change:

- `AGENTS.md`;
- the canonical failure-pattern register;
- source code, tests, schemas or generated runtime artifacts;
- workflows, binaries, transport files or staging directories;
- any institutional appointment, governance threshold or standing vocabulary;
- the seven audit artifacts.
