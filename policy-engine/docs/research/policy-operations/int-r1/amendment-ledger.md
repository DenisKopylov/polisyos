---
title: INT-R1 — Post-Audit Amendment Ledger
status: delivered
kind: deep-research
research_task: INT-R1
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@887bce985e6797c1a94dba24f33c6424ab09c0a5
authoritative_for:
  - mapping of INT-R1 audit findings and revision requirements to the amended research files
  - evidence that the independent audit acceptance checklist was applied item by item
  - preservation ledger for the audit's commended honesty constraints
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - merger or release approval
research_only: true
---

# INT-R1 — Post-Audit Amendment Ledger

## 1. Amendment basis and scope

This ledger records execution of the amendment specification in
`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-recommended-revision.md` and
the consolidation conditions in
`policy-engine/docs/research/policy-operations/audits/int-r1/int-r1-independent-audit.md`.

The amendment does not re-research or re-audit INT-R1. It narrows the delivered result to the
claims the audit verified. The audit bundle is unchanged. No code or test was added, and no file
outside the six INT-R1 research artifacts plus this ledger was modified.

Amended research files:

1. `../int-r1-obligation-coverage-and-open-world-completeness.md`
2. `repository-census-and-anchor-ledger.md`
3. `external-primary-source-ledger.md`
4. `open-world-impossibility-and-relative-coverage.md`
5. `artifact-and-state-machine-sketch.md`
6. `benchmark-and-edge-case-fixtures.md`

No R1–R11 item was declined.

## 2. Finding-to-amendment ledger

| Revision | Audit finding(s) | Disposition | What changed | Primary amended locations |
| --- | --- | --- | --- | --- |
| **R1** | `INT-R1-D-001`, `INT-R1-D-002` | **executed** | The positive formal result is renamed/recast as a **Conditional Relative-Inclusion Theorem**. Its deductive core is limited to fixed proposition/basis, generic traversal, assumed compiler semantic completeness, obligation binding, and assumed validator soundness. Independent reperformance, mutation, no-known-defeater review, governance, and currentness are separated into a governed admissibility protocol. Every theorem statement now says INT-R1 does not prove compiler semantic completeness or validator soundness. | main Executive Finding and §§4.2–4.4; formal note §§8–10 and §§14–16; artifact sketch §§1, 3.1, 4.1 |
| **R2** | `INT-R1-C-001` | **executed** | Every protected use must carry one per-scope disposition: `closed_by_competent_basis`, `open_under_unseen_extension`, or `closure_not_established`. Only the first may defeat the unseen-extension premise, and only for its exact owner/mandate/scope/purpose/audience/interval. No text says all PolicyOS domains are open or closable. | main Executive Finding and §§4.1, 7.1, 9.3; formal note §§3–5; artifact sketch `ClosurePremiseEvidence`; benchmark `GT-04`, `GT-05`, `F-19` |
| **R3** | `INT-R1-D-003` | **executed** | The executive result, capability census, formal note, artifact sketch, benchmark, and public projection all state that the pinned repository cannot issue `bounded_complete`. Missing independent checker/scorer, governance producer, envelope producer, instance layer, and bridges force current attempted protected use to `open_world_unresolved` and an existing fail-closed status. S0-GAP-02 is a dependency, never a self-populated field. | main Executive Finding, §§2.4, 4.4, 7, 9; census §§5.2–6; formal note §10; artifact sketch §§1, 3.1, 4.2, 7, 11; benchmark §§1, 3.3, 5.2, 10–12 |
| **R4** | `INT-R1-H-002` | **executed — selected blocked option** | `OM-01` is explicitly `prototype_blocked_on_instance_model` / blocked on **GY-GAP1**. The research identifies the needed pre-aggregation source-derived instance collection, semantic identity binding source/rule/scope/time/predicate/version, instance-to-class aggregation bridge, injection point, and independent pre-aggregation comparison point without freezing a wire schema. No passage represents OM-01 as currently runnable. | main §§2.4, 6.2; census §5.1; formal note §§10, 15; artifact sketch `ObligationCompilationBinding`; benchmark §§4, 6.1, 7, 10–12 |
| **R5** | `INT-R1-G-001` | **executed** | The categorical “enum is a capability-gating defect” verdict is removed. `PromotionObligationClass` is now a legitimate governed, versioned coarse vocabulary and declared denominator; the unsupported/defective use is treating it as the world boundary. GY-DEF5 is correctly described as a claim/docstring defect targeting “Universal.” The amendment explicitly forbids using INT-R1 to open, dissolve, or dynamically replace the enum. | main Executive Finding, §§2.3, 9.2, 10; census §§2.3–3; formal note §§2.2, 5.3; benchmark invalidation rules |
| **R6** | `INT-R1-B-001` | **executed by narrowing** | Detailed substantive attribution to *Normative Systems* is no longer load-bearing. The open catalog record is used only to establish bibliographic existence/orientation. The formal result stands on its own definitions and proof. A later page-exact primary citation may be added only by consolidation with lawful primary access. | main §3.1; external ledger §2 |
| **R7** | `INT-R1-A-002` | **executed** | The contributor-contract sentence now says the cited ranges require architecture, quality, testing, and documentation governance; it expressly denies that those ranges independently locate every canonical typed authority/runtime owner. | main §1.2; census §1 |
| **R8** | `INT-R1-F-002` | **executed** | `NO_COVERAGE_BLOCKER` is removed as a possible canonical output and retained only as explained historical pseudocode shorthand. It must not be persisted, exported, ordered, rendered, or consumed as promotion. The real meaning is absence of an additional coverage-specific refusal within the existing lattice. | main §7.3; artifact sketch §6.1; benchmark `GT-12`, `F-21`, invalidation rules |
| **R9** | `INT-R1-H-003` | **executed** | The broad phrase “defeats keyword tests” is replaced with a precise claim: the fixture is designed to defeat class-counting, marker-presence, normative-row presence, and generic accessibility-token checks that do not bind district-level source semantics. No claim is made about an undefined semantic keyword oracle. | main §6.2; benchmark §5.3 |
| **R10** | `INT-R1-I-003` | **executed** | The empirical statement is scoped to the **pinned W12.D/G5 proving-ground snapshot**: 13 typed blockers, zero grounded conversions, zero useful-design credit. It explicitly denies being an exhaustive statement about every experimental invocation in repository history. | main §2.4; census §9; formal note §6 |
| **R11** | `INT-R1-B-003` | **executed** | Stable identifiers are used for Cook (`10.1137/0207005`), corrigendum (`10.1137/0210045`), DeMillo et al. (`10.1109/C-M.1978.218136`), NASA MC/DC (`NASA/TM-2001-210876`, NTRS `20010057789`), and Ramdas et al. (`10.1214/23-STS894`, `arXiv:2210.01948`). Page ranges are not used as unsupported load-bearing evidence. | main §§3.2, 3.4; external ledger §§3, 8, 9 |

## 3. Acceptance checklist

The audit's §6 checklist is applied exactly below.

| Acceptance gate | Result | Amendment evidence |
| --- | --- | --- |
| Does the formal result clearly distinguish deductive inclusion from evidence/admissibility? | **yes** | main §§4.2–4.3; formal note §§8–9 |
| Does it say compiler completeness and validator soundness remain semantic assumptions rather than proved facts? | **yes** | Executive Finding; main §§4.2, 4.6; formal note §§8.4, 16 |
| Does each actual scope carry a closure-premise disposition? | **yes** | main §§4.1, 7.1; formal note §4; artifact `ClosurePremiseEvidence` |
| Does current standing explicitly deny issuance of `bounded_complete` at the pinned baseline? | **yes** | Executive Finding; main §§2.4, 4.4, 9.1; formal note §10; artifact §1; benchmark §1 |
| Is independent scoring/checking an actual dependency rather than self-attested metadata? | **yes** | main §§4.3–4.4, 7.1–7.2; artifact §§3.1, 4.1–4.2; benchmark §3 |
| Is OM-01 tied to an executable instance/aggregation layer or labeled blocked? | **yes — blocked option selected** | main §6.2; census §5.1; benchmark §4 and `OM-01` row |
| Is the enum verdict use-sensitive rather than categorical? | **yes** | main §2.3; census §3; formal note §2.2 |
| Are detailed *Normative Systems* claims primary-page anchored or narrowed? | **yes — narrowed** | main §3.1; external ledger §2 |
| Is `NO_COVERAGE_BLOCKER` expressly non-persisted and non-canonical? | **yes** | main §7.3; artifact §6.1; benchmark `GT-12`/`F-21` |
| Does the public δ rider expose basis, assumptions, remainder, currentness, and expiry? | **yes** | Executive Finding; main §4.6; formal note §12; artifact §11 |
| Does no revised sentence claim benchmark passage, capability, compliance, or authority? | **yes** | frontmatter deny-lists in all six files; main §§2.4, 9; benchmark §§1, 12 |

## 4. Commendation preservation ledger

The amendment preserves the audit's thirteen substantive strengths.

| No. | Preserved strength | Where it survives |
| ---: | --- | --- |
| 1 | The impossibility result is premise-relative rather than universal. | main §§4.1, 9.3; formal note §§3–5 |
| 2 | The result explicitly denies `C_v(B,a,s,p,t) = U(W,a,s,p,t)`. | main §4.2; formal note §§8.4, 12 |
| 3 | The five-row stopping taxonomy remains principled and P29-respecting. | main §4.7; formal note §14 |
| 4 | Search volume, randomization, TTL, independent review, and enum equality are not independent closure proofs. | main §4.1 and counterexamples; formal note §5 |
| 5 | Unknown remainder is explicit and never silently absorbed. | Executive Finding; main §§4.1, 4.5–4.6, 7.1; artifact `UnknownRemainder` |
| 6 | The benchmark forbids self-oracles and retains S0-GAP-02 as unresolved. | main §6.1; benchmark §3 |
| 7 | No benchmark was implemented or run; standing remains `semantic_test_missing`. | main §§2.4, 6.1; formal note §10; benchmark §§1, 12 |
| 8 | Red semantics set `protected_action_allowed = false` and `current_public_claim_allowed = false`. | main §6.3; benchmark §2 and acceptance rules |
| 9 | Public δ is always bounded relative to the declared obligation set and assumptions. | Executive Finding; main §4.6; formal note §12; artifact §11 |
| 10 | Correction is append-only and historical replay is preserved. | Executive Finding; main §§5, 7.4; formal note §13; artifact §§7–10; benchmark lifecycle fixtures |
| 11 | The supplied 14-member claim is corrected to the true 15-member denominator. | main §2.2; census §§1–2 |
| 12 | Coverage assessments feed one existing lattice and never auto-promote. | main §§4.5, 7.3; formal note §11; artifact §6 |
| 13 | Producer self-attestation cannot establish closure, independence, or bounded coverage; external-source transfers remain explicitly limited. | main §§3–5; external ledger throughout; artifact §§3.1, 4.1; benchmark §§3, 6.3 |

## 5. Frontmatter and capability integrity

The primary deliverable, the external-source ledger, the formal note, the artifact sketch, and
the benchmark specification retain `result_type: accepted_narrow_scope`. The repository census
retains its narrower factual `result_type: confirmed`; it does not use that label to claim the
missing INT-R1 capability.

All six amended research files:

- use `repository_branch: research/int-r1-amendment`;
- record `current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`;
- record
  `amended_after_audit: research/int-r1-independent-audit@887bce985e6797c1a94dba24f33c6424ab09c0a5`;
- remain `research_only: true`; and
- deny production implementation authorization, final wire/schema authority, canonical-owner
  appointment, authority grant, legal compliance, benchmark passage, and current
  `bounded_complete` capability.

## 6. Files and boundaries verified by this amendment

| Boundary | Amendment standing |
| --- | --- |
| Audit bundle | not edited |
| Code under `policy-engine/src/` | not edited |
| Tests | not added or edited |
| Other pre-existing documents/plans | not edited |
| Canonical owner/package/schema | not appointed or frozen |
| Existing status lattice | retained as sole authority lattice |
| Existing δ, denominator, validators, and promotion rules | not weakened or redefined |
| INT-R9 sequence-level multiplicity | explicitly deferred to INT-R9; not resolved here |
| Stage-0 custody kernel | preserved; no reopening requested |

## 7. Amendment result

All R1–R11 revisions were executed. The amendment's accepted result is narrower than the original
wording:

- open-world non-certifiability is conditional on an admissible unseen decisive extension;
- every protected scope requires an evidenced closure-premise disposition;
- the positive theorem proves inclusion/checking only under explicit compiler and validator
  semantic assumptions;
- independent review and testing govern reliance but do not create semantic truth;
- the current repository cannot issue `bounded_complete`;
- `open_world_unresolved` is the honest current fail-closed standing;
- OM-01 is blocked on GY-GAP1 and independent scoring on S0-GAP-02;
- the live enum remains a legitimate governed denominator, while its universal interpretation is
  rejected; and
- no benchmark passage, compliance, competence, authority, or implementation capability is
  claimed.

This satisfies the independent audit's amendment checklist for entry into the separate
consolidation pass. It does not itself authorize consolidation, implementation, merger, or
production use.
