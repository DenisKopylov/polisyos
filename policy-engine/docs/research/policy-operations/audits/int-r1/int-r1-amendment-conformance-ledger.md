---
title: "INT-R1 — Amendment Conformance Ledger"
status: delivered
kind: amendment-verification
research_task: INT-R1
verification_verdict: CONFORMS_WITH_GAPS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment-verification
verified_branch: research/int-r1-amendment
verified_commit: 66baff37c7f566fc770377ba6c66a8dc7b517ce0
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
authoritative_for:
  - machine-checkable disposition of INT-R1 amendment requirements R1-R11
  - disposition of the audit consolidation conditions and acceptance checklist
  - independent preservation check for all thirteen audit commendations
  - inventory of new amendment claims, weak plan anchors, and boundary results
may_not_use_for:
  - a new audit or alternative INT-R1 research result
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - merger, release, or production approval
research_only: true
---

# INT-R1 — Amendment Conformance Ledger

## 1. Disposition vocabulary

- **executed** — the required revision is present in the amended text at the required semantic
  strength.
- **partial** — part of the requirement landed, but a substantive element remains open.
- **declined** — the amendment explicitly declined the revision and gave a reason.
- **preserved** — an audited commendation survives in the amended files in substance.
- **gap** — a concrete amendment requirement or provenance condition remains unsatisfied.
- **not a gap** — an explicitly open research/implementation dependency that the amendment was
  required to preserve rather than solve.

No R1-R11 item is partial or declined. The only required correction left is the stale audit-head
SHA in amendment frontmatter. The two line-7 plan anchors are a separate minor navigation weakness.

## 2. R1-R11 conformance ledger

| Revision | Status | Required amendment | Independent evidence in amended text | Quoted fragment | Finding |
| --- | --- | --- | --- | --- | --- |
| **R1** | **executed** | Recast as conditional inclusion; identify compiler/validator semantics as assumptions; split deductive theorem from governed evidence protocol. | Primary Executive Finding and §§4.2-4.3; formal note §§8-9. | “Compiler semantic completeness and validator soundness are assumptions in that theorem. INT-R1 does not prove them.” / “These are evidence and admission criteria, not logical truth-generators.” | `INT-R1-V-001` |
| **R2** | **executed** | Require one per-scope closure disposition and make only competent closure defeat the impossibility premise. | Executive Finding; main §4.1; formal note §4; artifact `ClosurePremiseEvidence`; closure mutants. | “Only the first defeats the impossibility premise, and only within its stated boundary.” | `INT-R1-V-001` |
| **R3** | **executed** | State no current `bounded_complete` capability in executive, artifact sketch, and assessment introductions. | Main Executive, §§2.4, 4.4-4.5; formal §§10-11; artifact §§1-2, 3.1, 4.2, 6-7; benchmark §§1, 5.2, 8-12. | “PolicyOS cannot issue `bounded_complete`.” / “`bounded_complete` is a future governed assessment only.” | `INT-R1-V-001` |
| **R4** | **executed — blocked option** | Make OM-01 executable or mark it blocked on the named representation gap. | Main §6.2; census §5.1; formal §§10, 15; artifact pre-aggregation fields; benchmark §4 and OM-01 row. | “OM-01 standing = prototype_blocked_on_instance_model / blocking dependency = GY-GAP1.” | `INT-R1-V-001` |
| **R5** | **executed** | Treat the enum as a legitimate governed denominator; reject only universal-world use; do not license opening/dissolving it. | Main Executive and §2.3; census §§2.3-3; formal §§2.2, 5.3; kill/invalidation rules. | “Legitimate governed vocabulary. Gate participation does not remove Rule 12's exemption.” / “must not be opened or dissolved.” | `INT-R1-V-001` |
| **R6** | **executed by narrowing** | Page-anchor detailed *Normative Systems* attribution or make it non-load-bearing orientation. | Main §3.1; external ledger §2. | “The cited open catalog record verifies the work, not the original report's detailed page-level attribution. Those details are therefore not load-bearing here.” | `INT-R1-V-001` |
| **R7** | **executed** | Narrow the contributor-contract claim. | Main §1.2; census §1. | “The contributor contract supports architecture, quality, test, and documentation governance ... it does not itself locate or appoint every canonical authority owner.” | `INT-R1-V-001` |
| **R8** | **executed** | Keep `NO_COVERAGE_BLOCKER` noncanonical and nonpersisted. | Main §7.3; artifact §6.1; benchmark GT-12/F-21/invalidation rules. | “It must not be persisted, exported, ordered, or rendered as a status.” | `INT-R1-V-001` |
| **R9** | **executed** | Narrow “defeats keyword tests” to named weak oracles. | Main §6.2; benchmark §5.3. | “class-counting, marker-presence, and generic accessibility-token checks that do not bind district-level source semantics.” | `INT-R1-V-001` |
| **R10** | **executed** | Scope the proving-ground statement to the pinned W12.D/G5 snapshot. | Main §2.4; census §9; formal §6. | “At the pinned W12.D/G5 proving-ground snapshot ... This is a statement about that pinned snapshot, not an exhaustive claim about every experimental execution.” | `INT-R1-V-001` |
| **R11** | **executed** | Normalize citations to stable DOI/official report identifiers. | Main §§3.2, 3.4; external ledger §§3, 8, 9. | `10.1137/0207005`; `10.1137/0210045`; `10.1109/C-M.1978.218136`; `NASA/TM-2001-210876`; `10.1214/23-STS894`. | `INT-R1-V-001` |

### R1-R11 result

- Executed: **11**
- Partial: **0**
- Declined: **0**
- Silent omissions: **0**

## 3. Independent-audit §15 consolidation conditions

| No. | Condition | Status | Amended evidence |
| ---: | --- | --- | --- |
| 1 | Recast §4.2 as conditional relative inclusion, not discharge of compiler/validator assumptions. | **executed** | Main §4.2 and formal §8 explicitly name D4/D6 assumptions and deny proof of them. |
| 2 | Separate the deductive theorem from the evidence/admissibility protocol. | **executed** | Main §§4.2-4.3 and formal §§8-9 are separate sections with separate logical classifications. |
| 3 | Add per-scope closure-premise disposition. | **executed** | Three values, evidence requirements, effects, non-transfer rules, typed field, and benchmark mutants. |
| 4 | State current `bounded_complete` issuance is unavailable. | **executed** | Executive, capability census, formal current-standing section, artifact standing and future state, benchmark caveats. |
| 5 | Specify instance/aggregation layer or block OM-01. | **executed — blocked** | GY-GAP1 is named; required future layer is enumerated; no current-run claim remains. |
| 6 | Narrow enum defect to universal use, not the live governed vocabulary. | **executed** | Use-sensitive table; explicit no-open/no-dissolve rule; GY-DEF5 matched. |
| 7 | Add primary page support or narrow *Normative Systems*. | **executed — narrowed** | Detailed attribution made non-load-bearing bibliographic orientation. |
| 8 | Keep `NO_COVERAGE_BLOCKER` noncanonical. | **executed** | Explicit no persist/export/order/render/satisfaction/promotion rule. |
| 9 | Scope proving-ground evidence. | **executed** | Pinned W12.D/G5 wording and explicit history disclaimer. |
| 10 | Preserve public rider, red consequences, append-only history, and benchmark non-passage. | **executed** | Main Executive/§§4.6, 6.1-6.4, 7.4; formal §§12-14; artifact §§7-11; benchmark §§1-3, 8-12. |

### §15 result

All ten substantive conditions are executed. The stale audit-head frontmatter ref is outside the
numbered §15 list but inside the amendment working agreement and latest verification Check 5.

## 4. Recommended-revision §6 acceptance checklist

| Gate | Required answer | Verified answer | Evidence |
| --- | --- | --- | --- |
| Deductive inclusion distinguished from evidence/admissibility? | yes | **yes** | Main §§4.2-4.3; formal §§8-9. |
| Compiler completeness and validator soundness remain assumptions? | yes | **yes** | Executive, D4/D6, exact-limit paragraphs, honest δ rider. |
| Each actual protected use carries a closure disposition? | yes | **yes** | Main §4.1; formal §4; artifact `ClosurePremiseEvidence`; benchmark closure faults. |
| Current `bounded_complete` issuance denied? | yes | **yes** | Executive; main §§2.4, 4.4-4.5; artifact §1; formal §10; benchmark §1. |
| Independent scoring/checking is a dependency, not metadata? | yes | **yes** | S0-GAP-02 retained; producer-filled independence rejected; scorer/oracle refs may be absent and block. |
| OM-01 executable or blocked? | yes | **yes — blocked on GY-GAP1** | Main §6.2; benchmark §4 and prerequisite gate. |
| Enum verdict use-sensitive? | yes | **yes** | Main §2.3; census §3; formal §2.2. |
| *Normative Systems* page-anchored or narrowed? | yes | **yes — narrowed** | Main §3.1; external §2. |
| `NO_COVERAGE_BLOCKER` nonpersisted/noncanonical? | yes | **yes** | Main §7.3; artifact §6.1; benchmark GT-12/F-21. |
| Public δ rider exposes basis, assumptions, remainder, currentness, expiry? | yes | **yes** | Executive; main §4.6; formal §12; artifact §11. |
| No benchmark passage, capability, compliance, or authority claim? | yes | **yes** | Frontmatter deny-lists; capability tables; benchmark §§1, 12; maturity/kill rules. |

### Acceptance-checklist result

Substantive yes answers: **11/11**.

## 5. Thirteen commendations — independent preservation check

This table uses the independent audit's actual commendation IDs. The quoted fragments are from the
amended artifacts, not from the amendment ledger.

| Audit commendation | Status | Surviving amended passage | Quoted fragment / verification |
| --- | --- | --- | --- |
| `INT-R1-A-001` — repository evidence base intact | **preserved** | Repository census §§1-6; primary §2. | “The source anchors below remain the evidence base”; exact conditionality, partition, N9, P29, owner, and capability anchors remain. Compare `d152565d...978e6b958` shows no anchored core source changed. |
| `INT-R1-A-003` — no broken or deceptively adjacent core anchor | **preserved** | Census anchors and this verification's changed-anchor pass. | Core claims remain paired with the same source ranges; no contrary source was found. The only weak set is the two truthful line-7 plan metadata anchors, separately recorded as V-005. |
| `INT-R1-B-002` — disciplined external transfers and non-transfers | **preserved** | External ledger §§2-11; primary §3. | “No audited source supplies a theorem of global obligation completeness”; each literature family retains Supported/Transfer/Non-transfer boundaries. |
| `INT-R1-C-002` — search, review, enum, TTL, randomization not closure proofs | **preserved** | Main §4.1/counterexamples; formal §5. | “Search volume, randomization, independent repetition over a shared basis, exact enum equality, and an unexpired TTL do not independently supply the missing closure premise.” |
| `INT-R1-D-004` — principled five-row P29 stopping taxonomy | **preserved** | Main §4.7; formal §14. | Rows still distinguish complete-by-construction owned traversal, conditional relative inclusion, semantic assumption plus evidence, governance judgment, and explicit unknown/impossibility. |
| `INT-R1-E-001` — self-oracle ban and S0-GAP-02 deferral | **preserved** | Main §6.1; benchmark §3 and invalidation rules. | “Expected obligations must be authored ... by an independent path ... and never generated from the compiler under test.” / “Independent scoring remains blocked on S0-GAP-02.” |
| `INT-R1-E-002` — explicit non-passage | **preserved** | Main §§2.4, 6.1; formal §10; benchmark §§1, 12. | “No benchmark was implemented or run; current standing remains `semantic_test_missing`.” |
| `INT-R1-E-003` — producer self-attestation cannot establish bounded coverage | **preserved** | Main counterexamples; artifact §§1, 3.1, 4.1; benchmark GT-03/F-20. | “A producer-populated field that says ‘independent’ is not evidence of independence.” / “Populated fields do not establish validity.” |
| `INT-R1-F-001` — one lattice and no auto-promotion | **preserved** | Main §§4.5, 7.3; formal §11; artifact §6. | “The existing PDC/Atlas lattice remains the only authority lattice.” / future positive means only “absence of an additional coverage blocker,” “never SATISFIED and never promoted by itself.” |
| `INT-R1-H-001` — required artifacts, state machine, challenge/reissue, statuses, fixtures | **preserved** | Main §§6-7; artifact §§3-11; benchmark §§5-10. | Both typed artifacts remain; challenge and perturbation records remain; lifecycle states/owners/clocks/public meanings remain; F-01 through F-10 remain enumerated. |
| `INT-R1-H-004` — strong red semantics | **preserved** | Main §6.3; benchmark §2 and acceptance rules. | `protected_action_allowed = false` and `current_public_claim_allowed = false`; warning-only/backend-red/public-green is still benchmark failure. |
| `INT-R1-H-005` — clean research-only change boundary | **preserved** | Amendment diff and all frontmatter deny-lists. | The amendment changes only six INT-R1 research artifacts and adds one ledger; no source, test, audit, plan, or other existing document changed. |
| `INT-R1-I-002` — other material supplied-orientation facts verified | **preserved** | Census §§1-6, 9; primary §2; formal §§1-2, 6. | The amended corpus retains the explicit maintained assumptions, exact enum partition, five-profile count, P29/kernel/CTM constraints, scoped W12.D/G5 evidence, and unavailable empirical miss-rate conclusion. |

### Additional required strength — caught 14/15 error

The audit classified the supplied 14-member statement as a material orientation error correctly
caught by the researcher rather than as a commendation. The amendment preserves the correction:

> “The supplied orientation said 14 classes. The pinned source has 15, including
> `VALUE = "value"`.”

This appears in primary §2.2 and census §§1-2.

### Commendation result

Preserved in substance: **13/13**.

None survives only as a heading. The cited fragments retain the limiting proposition, the failure
consequence, or the explicit non-transfer that made the original item commendable.

## 6. Added-claim classification ledger

| Added amendment statement | Class | Evidence basis | Conformance result |
| --- | --- | --- | --- |
| `closed_by_competent_basis` / `open_under_unseen_extension` / `closure_not_established` | required semantic narrowing | R2 / C-001 | permitted and applied |
| Only competent closure defeats the indistinguishability premise for exact scope/time/purpose | required consequence | R2 | permitted |
| Current `open_world_unresolved` is steady state, not placeholder | required current-capability consequence | R3 / D-003; Atlas Rev 3.10 | verified |
| `GY-DEF5` targets universal wording, not enum behavior | required narrowed repository reading | R5 / G-001; GY Rev 23 | verified |
| Enum must not be opened/dissolved under INT-R1 | protective consequence of R5 | GY Rev 23 and audit | verified |
| `GY-GAP1` blocks current OM-01 | required selected disposition | R4 / H-002; GY Rev 23 | verified |
| Pre-aggregation instance identity/aggregation fields | noncanonical implementation handoff | R4 required semantic minimum | permitted; expressly unfrozen |
| `bounded_current_future` lifecycle name | local explanatory notation | R3 future-only consequence | permitted; explicitly unreachable/noncanonical |
| Closure/self-attestation/projection mutants and extra fixtures | benchmark-design consequences | R2-R4/R8-R9 | permitted; no execution claim |
| Stable DOI/report identifiers | citation normalization | R11 | verified |
| Audit branch HEAD is `0893a739...` | provenance claim | contradicted by branch comparison | **gap — actual HEAD is `887bce98...`** |

## 7. Audit §15 condition-to-R mapping

| §15 condition | Corresponding revision/finding | Final status |
| ---: | --- | --- |
| 1 | R1 / D-001 | executed |
| 2 | R1 / D-002 | executed |
| 3 | R2 / C-001 | executed |
| 4 | R3 / D-003 | executed |
| 5 | R4 / H-002 | executed by block |
| 6 | R5 / G-001 | executed |
| 7 | R6 / B-001 | executed by narrowing |
| 8 | R8 / F-002 | executed |
| 9 | R10 / I-003 | executed |
| 10 | preservation conditions / C-002, E-001, E-002, H-004 | executed |

## 8. Frontmatter and anchor conformance ledger

### 8.1 Frontmatter fields

| Field | Expected | Actual | Status |
| --- | --- | --- | --- |
| `result_type` | retain narrow result | `accepted_narrow_scope` in five research-result files; `confirmed` only in factual census | conforms |
| `repository_branch` | `research/int-r1-amendment` | exact | conforms |
| `current_repository_commit` | `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d` | exact | conforms |
| `research_only` | `true` | exact | conforms |
| `may_not_use_for` | exclude capability, current `bounded_complete`, authority, compliance, benchmark, implementation | present across amended research files | conforms |
| `amended_after_audit` | actual audit branch HEAD | `research/int-r1-independent-audit@0893a739...` | **gap** |
| actual audit branch HEAD | — | `887bce985e6797c1a94dba24f33c6424ab09c0a5` | verified by identical branch comparison |

### 8.2 Weak metadata-anchor inventory

| Unique weak anchor | Files/claim families using it | Support verdict | Severity |
| --- | --- | --- | --- |
| `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` | current `bounded_complete` refusal; DS17 unresolved steady state; Atlas projection handoff | supports exactly, but lands on Revision 3.10 metadata rather than the substantive DS17 block | minor |
| `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7` | GY-DEF5 enum protection; GY-GAP1/OM-01 block | supports exactly, but lands on Revision 23 metadata rather than the registered defect/gap blocks | minor |

No other anchor in the amendment was found to cite frontmatter/revision prose in place of a
substantive block for a newly added claim.

## 9. Boundary conformance ledger

| Boundary | Verification evidence | Status |
| --- | --- | --- |
| Audit bundle untouched | base-to-head changed-file list excludes `audits/int-r1/` | conforms |
| No `policy-engine/src/` change | changed-file list | conforms |
| No test change/addition | changed-file list | conforms |
| No other pre-existing document changed | changed-file list contains six target artifacts plus new amendment ledger only | conforms |
| No canonical owner appointed | owner language remains “prefer,” “unresolved,” “to be ratified”; deny-lists explicit | conforms |
| No package/API/wire/schema frozen | artifact/benchmark paths and fields marked illustrative/noncanonical/unfrozen | conforms |
| One status lattice | positive branch only removes an additional refusal; `NO_COVERAGE_BLOCKER` banned as state | conforms |
| Existing δ/denominator/validators not weakened | research expressly denies changing them and protects enum | conforms |
| INT-R9 multiplicity not resolved | primary §10 explicitly defers sequence-level multiplicity to INT-R9/INT-R10 | conforms |
| Stage-0 kernel not weakened | K05/K06/K12/K16 consequences retained; no reopening requested | conforms |
| Benchmark remains unimplemented | repeated `semantic_test_missing`; GY-GAP1 and S0-GAP-02 blocks | conforms |

## 10. Machine-readable disposition summary

```yaml
verification_verdict: CONFORMS_WITH_GAPS
revisions:
  executed: 11
  partial: 0
  declined: 0
consolidation_conditions:
  executed: 10
  open: 0
acceptance_checklist:
  yes: 11
  no: 0
commendations:
  preserved: 13
  lost: 0
findings:
  blocking: 0
  material: 0
  minor:
    - INT-R1-V-004  # stale audit HEAD in amended_after_audit
    - INT-R1-V-005  # truthful but weak line-7 plan anchors
required_before_full_conformance:
  - replace amended_after_audit SHA 0893a739e4739a6cd31dd95bc0b88526e1ff29ae
    with 887bce985e6797c1a94dba24f33c6424ab09c0a5
recommended_anchor_hygiene:
  - replace Atlas plan line-7 metadata citations with substantive DS17 block anchors
  - replace GY plan line-7 metadata citations with substantive GY-DEF5/GY-GAP1 block anchors
re_research_required: false
re_audit_required: false
```

## 11. Final conformance statement

The amendment's substantive self-report is confirmed: it executed R1-R11 and retained the audit's
thirteen commended strengths in the amended texts themselves. The primary document's size
reduction removed repetition and overstatement rather than the qualifications. The amendment is
not fully conformant only because its audit-provenance field pins an earlier audit commit instead
of the actual audit branch HEAD. Correcting that SHA is a mechanical amendment, not new research.
