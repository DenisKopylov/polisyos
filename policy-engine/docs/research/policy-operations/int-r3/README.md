---
task_id: INT-R3
stage: 1
artifact_role: package_index
status: amended_after_independent_audit
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
research_branch: research/int-r3-research
amendment_branch: research/int-r3-amendment
authoritative_for:
  - int_r3_package_navigation
may_not_use_for:
  - operator_comprehension_claim
  - implementation_closure
---

# INT-R3 package — Authority UI comprehension

This directory supports the stage-1 research deliverable
[`../int-r3-authority-ui-comprehension-benchmark.md`](../int-r3-authority-ui-comprehension-benchmark.md).

The package specifies an `AuthorityUIComprehensionBenchmark`. It does **not** report a human-subject
result. Until the instrument is executed with real target operators against a frozen build, the
comprehensibility and actionability of the PolicyOS surfaces are `not_established`.

## Package map

| File | Purpose |
| --- | --- |
| `repo-baseline.md` | Audited stage-1 baseline as originally delivered. |
| `external-evidence-ledger.md` | Stage-1 external-practice synthesis. |
| `benchmark-specification.md` | Stage-1 protocol, scenario grammar, metrics and validity case. |
| `finding-register.md` | Stage-1 classified findings. |
| `pattern-pass.md` | Stage-1 pass over `P01`–`P38`. |
| `contract-coverage.md` | Stage-1 and amendment contract trace. |
| `amendment-ledger.md` | Stage-3 disposition for all 23 audit findings and reconciliation arithmetic. |
| `amendment-specification.md` | Superseding clauses for standing, feasibility, predicates, exclusion, novel constructs, transfer and blocker timing. |
| `repository-baseline-amendment.md` | Corrected source anchors, disclosed search scope, current/planned split and stale DS6 allocation. |
| `external-source-ledger.md` | Survey digests and stable claim-to-primary-source anchors for `EXT-01`–`EXT-16`. |

## Amendment precedence

The independent audit is under
[`../audits/int-r3/`](../audits/int-r3/). The stage-3 files above are additive and preserve the
audited stage-1 text. Where a stage-3 file explicitly names and supersedes a stage-1 clause, the
stage-3 clause is the effective package state. Unnamed stage-1 clauses remain unchanged.

## Standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
gate_basis: DS12_first_public_signature_gate_at_dc7bdf79a
comprehension_claim_use: NO_GO
int_r3_is_ds12_gate_input: false
evidence_standing: not_established
```

`gate_standing` is the first-public-signature gate. `comprehension_claim_use` is the separate rule
preventing this package from being cited as human-comprehension evidence.

## Boundary

The benchmark contract and the requirement to establish comprehension of PolicyOS's own authority
projections are **OWN**. Recruitment, research ethics, employment conditions, and appointment of
accountable operational authorities are external institutional functions that PolicyOS must
**INTEGRATE** as typed evidence when a real study is commissioned. Preference research and general
product sentiment are outside this benchmark's correctness claim.

The prior DS6 instrument allocation is classified `stale`: DS6 closed at `176276ef0` without the
instrument. The current instrument owner is `unowned`, and allocation is routed to the human
principal. This package appoints nobody.
