---
task_id: INT-R3
stage: 1
artifact_role: package_index
status: research_complete
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
branch: research/int-r3-research
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
| `repo-baseline.md` | What an operator is shown today, exact repository coordinates, reusable primitives, and current gaps. |
| `external-evidence-ledger.md` | The five commissioned surveys, primary-source anchors, transfer arguments, disagreements, and thin areas. |
| `benchmark-specification.md` | Implementable instrument, scenario grammar, ground truth, six mandatory metrics, accessibility conditions, and analysis plan. |
| `finding-register.md` | Every material finding classified before hand-back. |
| `pattern-pass.md` | Recorded pass over `P01`–`P38`, including `P35`–`P38`. |
| `contract-coverage.md` | Trace from the governing deliverable contract and hand-back requirements to committed sections. |

## Standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
evidence_standing: not_established
```

`gate_standing: NO_GO` applies to any claim that operator comprehension has been established, and to
using comprehension as closure evidence. It does not by itself adjudicate unrelated publication
gates.

## Boundary

The benchmark contract and the requirement to establish comprehension of PolicyOS's own authority
projections are **OWN**. Recruitment, research ethics, employment conditions, and appointment of
accountable operational authorities are external institutional functions that PolicyOS must
**INTEGRATE** as typed evidence when a real study is commissioned. Preference research and general
product sentiment are outside this benchmark's correctness claim.
