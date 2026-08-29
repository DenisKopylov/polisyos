---
task_id: INT-R3
stage: 1
artifact_role: contract_coverage
status: complete
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
| 2. Current Repo Baseline | main §2 and `repo-baseline.md` |
| 3. External Research Baseline | main §3 and `external-evidence-ledger.md` |
| 4. Result | main §4 and `benchmark-specification.md` |
| 5. Counterexamples And Failure Modes | main §5 |
| 6. Benchmark Or Fixture Proposal | main §6 and benchmark §§5–9 |
| 7. Artifact Contract Sketch | main §7 |
| 8. Later Integration Handoff | main §8 |
| 9. Promotion And Kill Rules | main §9 |
| 10. Open Questions For Consolidation | main §10 |

## Operational closure addendum

| Required item | Committed location |
| --- | --- |
| boundary census | main addendum §A1 and `repo-baseline.md` |
| real operator workflow | main addendum §A2 |
| state machine | main addendum §A3 |
| typed artifacts | main §7 and addendum §A4 |
| edge-case fixtures | main addendum §A5 |
| tabletop / fault injection | main addendum §A6 |
| capstone linkage | main addendum §A7 |

## Hand-back requirements

| Requirement | Coverage |
| --- | --- |
| one Markdown deliverable plus `int-r3/` directory | exact eight-file package below |
| all six metrics with implementable denominators | `benchmark-specification.md` §8 |
| defensible ground truth and adjudication | benchmark §4 |
| accessible path inside the instrument | benchmark §6 |
| confident-and-wrong measurement | benchmark §8.6 |
| current operator-surface inventory with coordinates | `repo-baseline.md` |
| explicit `not_established` until a real run | main result, README and finding register |
| every material finding classified | `finding-register.md` |
| standing on three separate `W4-K05` axes | main, README and finding register |
| Pattern Pass recorded | `pattern-pass.md` |
| no human-subject overclaim | benchmark §10 and main §4 |
| mandatory pre-build input / red-first constraints | benchmark §2 |
| no edits to source, workflows, `AGENTS.md` or pattern register | branch tree census/readback |
| committed-branch head, file set and blob identities | post-write GitHub readback |

## Exact intended file set

```text
policy-engine/docs/research/policy-operations/int-r3-authority-ui-comprehension-benchmark.md
policy-engine/docs/research/policy-operations/int-r3/README.md
policy-engine/docs/research/policy-operations/int-r3/repo-baseline.md
policy-engine/docs/research/policy-operations/int-r3/external-evidence-ledger.md
policy-engine/docs/research/policy-operations/int-r3/benchmark-specification.md
policy-engine/docs/research/policy-operations/int-r3/finding-register.md
policy-engine/docs/research/policy-operations/int-r3/pattern-pass.md
policy-engine/docs/research/policy-operations/int-r3/contract-coverage.md
```

## Prohibited changes

This stage does not change:

- `AGENTS.md`;
- the canonical failure-pattern register;
- source code, tests, schemas or generated runtime artifacts;
- workflows, binaries, transport files or staging directories;
- any institutional appointment or standing decision.
