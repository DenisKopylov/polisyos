---
title: INT-R10 — Claim-Evidence Ledger
status: delivered
kind: independent-audit
research_task: INT-R10
audited_branch: research/int-r10-family-wise-risk-composition
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
overall_verdict: NO_GO
research_only: true
authoritative_for:
  - exhaustive independent verification ledger for load-bearing INT-R10 claims
  - traceability from each theorem, repository, transfer, fixture, and standing claim to its verification method
  - separation of confirmed abstract results from refuted pinned-source applications
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - replacement for the audited research deliverable
  - assertion that a live family projection exists
---

# INT-R10 — Claim-Evidence Ledger

## 1. Verdict vocabulary

- `confirmed` — the claim follows from the cited source or proof as written.
- `confirmed_narrower` — a bounded version is valid; the report's broader wording is not.
- `refuted` — an actual counterexample or stronger source premise defeats the claim.
- `not_implemented` — the research rule may be coherent, but no live capability supplies it.
- `material_revision` — the core direction survives but a premise, proof step, or reproducibility
  condition must change.
- `commendation` — verified strength that consolidation should preserve.

The ledger treats “three valid statements each bounded by `delta` imply a union bound of
`3 * delta`” and “the pinned canonical owner exposes no stronger information than those three
statements” as different claims. The first is true; the second is false.

---

## 2. Formal and arithmetic claims

| ID | Load-bearing claim | Audited location | Verification method | Verdict | Consequence |
| --- | --- | --- | --- | --- | --- |
| C-001 | `V_i = R_i ∩ P_i ∩ W_i` and `V_F = union_i V_i` express false first promotion under stop-on-first-positive. | primary §§1.2, 4.2 | Event-algebra reconstruction, including unreached members and prior negatives/refusals. | confirmed | Safe for INT-R9. |
| C-002 | The conditional union inequality applies to reached-member events. | primary §4.2 | Apply Boole's inequality under the common conditional law `A_F`. | confirmed | No common null or independence required. |
| C-003 | Prospective caps with `sum alpha_i <= delta_F` imply family control if each local theorem is valid at its cap under the same assumptions. | primary §4.2 | Four-line proof audit. | confirmed | Theorem A survives. |
| C-004 | Cap enforcement before execution is a theorem premise. | Executive, §§4.2, 4.5, 7.4 | Outcome-dependent cap counterexample; source ordering check. | confirmed | After-the-fact spend is not evidence. |
| C-005 | Theorem A requires no common null, estimand, exchangeability, or independence. | Executive, §§3.1, 4.2 | Inspect proof: none of those objects occurs. | confirmed | Correct heterogeneous-event transfer. |
| C-006 | Local theorem assumptions remain local and are not erased by union accounting. | §§3.4–3.5, 4.2 | Compare local certificate premise with union proof. | confirmed | External statistical assumptions remain load-bearing. |
| C-007 | Family control remains conditional on obligation completeness and validator soundness. | Executive, §§1.2, 4.10, 8.3 | Compare with ledger constant and INT-R1 theorem. | confirmed | Preserve explicit rider. |
| C-008 | From only three coarse marginal bounds `P(V_i|A_F) <= delta`, `3 * delta` is attainable for `3delta <= 1`. | §§2.4, 4.3 | Construct disjoint reached false-promotion events with `A_F = Omega`. | confirmed_narrower | Valid only after discarding stronger canonical structure. |
| C-009 | `3 * delta` is sharp from the information exposed by the pinned canonical owner. | Executive, §§2.4, 4.1, 4.3, 4.4 | Enumerate schedule/class source; derive all-path envelope. | **refuted** | Blocking `INT-R10-B-001`. |
| C-010 | Live `delta = 1/100` therefore yields a strongest baseline family bound `3/100`. | Executive, §§2.4, 4.4, 4.10, 8.2, 10 | Exact `Fraction` census and Basel-series bound. | **refuted** | Withdraw all `3/100` handoffs. |
| C-011 | Each ordinary scope can spend event risk all the way to root `delta`. | Implied by §§2.4, 4.4, fixture §7.3 | Source formula: one global local ordinal, class weights, mass <=1. | **refuted** | Root delta is a loose policy ceiling. |
| C-012 | One mass-one scope's scheduled probabilistic envelope is strictly below `(3/20)delta`. | Audit falsifier, not claimed by report | Max expanded class weight `3/20`; `c_B < 6/pi^2`; global ordinal. | confirmed | Must be included in revised composition. |
| C-013 | Three pinned scopes' schedule envelopes are strictly below `(9/20)delta`. | Audit falsifier | Union over the three deterministic all-path local envelopes. | confirmed | Shows `3delta` is not source-sharp. |
| C-014 | Equal `delta_F/3` effective caps are a valid sufficient future design if truly enforced. | §§4.5, 6, fixture | Substitute caps into Theorem A. | confirmed_narrower | Sufficient, not shown necessary. |
| C-015 | Equal `delta_F/3` caps are required to repair the live three-scope arithmetic. | Executive, §§4.5, 6 | Compare with existing schedule envelope. | refuted | Re-research cap need before design. |
| C-016 | The Basel-square schedule can run inside a smaller effective local cap. | §§4.5, 7.4 | Algebraically true as a hypothetical rescaling. | confirmed_narrower | Engineering possibility, not implemented. |
| C-017 | The live ledger already accepts an effective family cap parameter. | Implied by future sketch only | Source search and signature review. | not_implemented | Report correctly says extension required. |
| C-018 | No-refund is sufficient for the fixed cap vector. | §4.6 | Pathwise cap accounting; unused allocations retire. | confirmed | Safe conservative protocol. |
| C-019 | No recycling theorem can ever exist. | expressly disclaimed | Read §4.6 and fixture terminal table. | not claimed | Good boundary. |

---

## 3. Adaptive-continuation claims

| ID | Load-bearing claim | Audited location | Verification method | Verdict | Consequence |
| --- | --- | --- | --- | --- | --- |
| C-020 | Outcome-dependent repair makes later member procedures adaptively selected. | Executive, §§4.7–4.8 | Trace INT-R9 general-repair rule against prior revealed outcome. | confirmed | Fixed-plan theorem does not apply automatically. |
| C-021 | `alpha_i(H_{i-1})` must be predictable/history-measurable. | §§3.4, 4.7, source §4.3 | Compare with conditional expectation proof and online-FWER/e-process premises. | confirmed_narrower | Primary theorem says “determined before” but needs formal measurability. |
| C-022 | `R_i` is measurable from the prior family history. | Used silently in §4.7 | Inspect tower identity. | material_revision | Must be stated for the equality to follow. |
| C-023 | The displayed tower identity follows exactly as written. | §4.7 | Conditional-expectation derivation. | material_revision | Requires filtered-space and `R_i` measurability; expectations need `|A_F`. |
| C-024 | A pathwise total `sum alpha_i(H_{i-1}) <= delta_F` is feasible. | §4.7 | Fixed caps and conservative no-refund witness. | confirmed | Constraint is not fictitious. |
| C-025 | Pathwise cap accounting alone validates outcome-selected repair. | explicitly denied | Read §4.7 and source ledger. | not claimed | Strong point. |
| C-026 | History-conditional local validity under the actual selector is sufficient. | §4.7 | Corrected tower-property proof. | confirmed_narrower | Preserve after formalization. |
| C-027 | “Or an equivalent uniform/selection-aware theorem” is itself a verified theorem class. | §4.7 | Search for target, assumptions, registry profile, verifier, and equivalence criterion. | refuted as closure evidence | Material escape clause. |
| C-028 | Adaptation is not intrinsically impossible. | §4.7 | Fixed/conditional e-process and uniform-theorem examples establish possibility in principle. | confirmed | Safe qualitative conclusion. |
| C-029 | Current INT-R9 general repair has a family numeric theorem. | expressly denied | Registry and protocol audit. | not_implemented | Safe current handoff is “blocked.” |

---

## 4. Canonical repository claims

| ID | Load-bearing claim | Verification method | Verdict | Evidence |
| --- | --- | --- | --- | --- |
| C-030 | N9's only admissible risk scope is per problem binding. | Read function/docstring. | confirmed | `promotion_sequence.py:356-375`. |
| C-031 | Scope key is `design-problem:<design_problem_id>`. | Read constructor. | confirmed | same. |
| C-032 | `ConfidenceRiskBudgetScope` is one stable non-resettable budget. | Read class and scope ID derivation. | confirmed | `confidence_ledger.py:156-184`. |
| C-033 | Three distinct problem IDs yield three distinct canonical scope IDs, assuming distinct content bindings. | Recompute content-derived inputs. | confirmed | scope constructor and ID model. |
| C-034 | Root binds each scope to registry, schedule, delta, assumptions, and immutable history. | Read root model/session initialization. | confirmed | `confidence_ledger.py:518-557`. |
| C-035 | Local ordinal and prior spend use only current-scope events. | Read `start_check()`. | confirmed | `confidence_ledger.py:1301-1368`. |
| C-036 | Risk is durably appended before owner execution. | Read through append and `execute_check()` transition. | confirmed | `confidence_ledger.py:1356-1382`; audited range often ended too early. |
| C-037 | Receipt validation recomputes exact spend and contiguous ordinals. | Read `_validate_receipt_spend`. | confirmed | `confidence_ledger.py:3880-4025`. |
| C-038 | The schedule formula uses exact `Fraction` arithmetic and certified coefficient `76614/126025`. | Source and exact calculation. | confirmed | `confidence_ledger.py:20-52`, `3998-4015`. |
| C-039 | Obligation pools totally partition the enum and pool weights total exactly one. | Read registry validator and TOML. | confirmed | `confidence_ledger.py:330-390`; TOML 18–50. |
| C-040 | Expanded class weights also total one. | Enumerate `obligation_weights`. | confirmed | `confidence_ledger.py:405-419`. |
| C-041 | Maximum expanded live class weight is `3/20`. | Full registry enumeration. | confirmed | calibration pool. |
| C-042 | Live registry is 232 lines. | Fetch beyond EOF; lines 225–240 returned exactly 225–232. | confirmed | registry blob `23f4b82...`. |
| C-043 | Proof-profile counts are 2 ineligible, 1 unavailable, 1 deterministic, 1 constant-unit e-process. | Full set enumeration. | confirmed | registry 53–90. |
| C-044 | Instrument count is also five. | Full set enumeration. | refuted if inferred | There are 13 instruments; report generally says profiles, so no main-text error. |
| C-045 | Two schedules use `basel_square_v1`. | Full set enumeration. | confirmed | registry 8–16. |
| C-046 | Delta is exactly `1/100`. | Rational registry value. | confirmed | registry 1–6. |
| C-047 | No `cross_scope`, `family_wise`, or `parent_scope` symbol occurs in the ledger. | Three exact source searches. | confirmed | no matches. |
| C-048 | GY-GAP2 records missing cross-scope composition and says N11 scope identity is not wrong. | Read substantive block. | confirmed | `GY-engine-subordination.md:2439-2463`. |
| C-049 | The report's `GY...:1-10` anchor lands on the substantive block. | Follow range. | refuted | It lands on frontmatter/revision metadata. |
| C-050 | Proving ground is 0/13, useful-design rate 0, D3.8 unbuilt. | Read governing decision. | confirmed | universal vision 390–398. |
| C-051 | Relevant owner-verified probabilistic profiles are unavailable. | Enumerate profiles and instruments. | confirmed | registry 53–166. |
| C-052 | The only executable e-process can satisfy promotion obligations. | Read profile and role. | refuted | constant-unit profile is conformance-only and `permits_obligation_satisfaction=false`. |
| C-053 | No empirical family calibration base exists. | Proving-ground and registry review. | confirmed | no governed positive history. |
| C-054 | Current source implements a canonical family projection. | Search source/artifacts. | refuted | GY-GAP2 remains `contract_missing`. |

---

## 5. R1 and governance claims

| ID | Claim | Verification method | Verdict | Consequence |
| --- | --- | --- | --- | --- |
| C-055 | The report addresses the exact R1 family event. | Compare §§1.2/4.2 with R1 item 1. | confirmed | Requirement 1 met. |
| C-056 | It preserves canonical scope identity. | Compare design pattern and anti-duplication rules. | confirmed | Requirement 2/7 strength. |
| C-057 | It defines refusal/void/dispute/completion effects. | Inspect §4.6 and fixture §6. | confirmed at research level | Requirement 4 criterion strong. |
| C-058 | Those effects are enforced today. | Search live source. | not_implemented | Baseline remains blocked. |
| C-059 | It proves exact aggregate composition for the pinned owner. | Audit §4.3/4.4 against schedule. | refuted | Requirement 5 fails. |
| C-060 | It narrows current adaptive repair honestly. | Read §§4.8/8.2. | confirmed | INT-R9 may cite the block. |
| C-061 | It reuses the confidence ledger rather than creating a second owner. | Structural review. | confirmed | Preserve. |
| C-062 | A live verifier can emit the positive family projection today. | Search source and artifacts. | not_implemented | Requirement 8 positive capability absent. |
| C-063 | The negative absence of family capability is live-reproducible. | Scope/root/search/GY checks. | confirmed | Baseline blocker is real. |
| C-064 | The mandatory falsifier is blocked at baseline. | Execute source trace conceptually. | refuted | Report correctly says it is not blocked. |
| C-065 | The §4.11 self-matrix proves all eight requirements are closed. | Independent grading. | refuted | It mixes theorem, future criterion, and current capability. |

---

## 6. External transfer claims

| ID | Method/source claim | Primary-source check | Verdict |
| --- | --- | --- | --- |
| C-066 | Holm controls strong FWER for valid p-values without favorable dependence. | Holm 1979. | confirmed |
| C-067 | Holm is a current PolicyOS procedure. | Repository search. | not_implemented |
| C-068 | Online Bonferroni/predictable allocation transfers; stronger online methods require independence/local dependence. | Tian & Ramdas 2021. | confirmed |
| C-069 | Pocock/O'Brien–Fleming/Lan–DeMets boundaries apply directly across heterogeneous problems. | Primary designs inspect one accumulating trial/statistic/information time. | refuted; report correctly denies |
| C-070 | Their aggregate-procedure lesson transfers. | Same primary sources. | confirmed |
| C-071 | Confidence sequences/e-processes survive stopping relative to their valid filtration/process. | Howard et al.; Ramdas et al. | confirmed |
| C-072 | An anytime-valid label survives arbitrary outcome-based process selection. | Same sources. | refuted; report correctly denies |
| C-073 | E-values can be averaged for one null under arbitrary dependence. | Vovk & Wang 2021. | confirmed |
| C-074 | E-values can be multiplied sequentially without conditional validity or independence. | Vovk & Wang 2020. | refuted; report correctly denies |
| C-075 | Existing e-value theory automatically supplies strong FWER over PolicyOS heterogeneous authority errors. | Source-target comparison. | refuted; report correctly says not automatic |
| C-076 | Classical Sidak product threshold is exact under independence. | Product identity. | confirmed; report should state explicitly |
| C-077 | Sidak 1967 supplies arbitrary-dependence product control. | Primary paper is multivariate-normal rectangle inequality. | refuted; report does not claim this but wording is broad |
| C-078 | Selective inference constrains interpretation of first passing result. | Fithian et al. | confirmed |
| C-079 | Selective inference creates the missing ledger owner. | Source/repository comparison. | refuted; report correctly denies |

---

## 7. Fixture and artifact claims

| ID | Claim | Verification method | Verdict | Consequence |
| --- | --- | --- | --- | --- |
| C-080 | Positive fixture requires effective cap enforcement before owner execution. | Inspect assertions and FWC-NEG-18/19. | confirmed | Strong P29 design. |
| C-081 | Positive fixture can pass at baseline. | Compare to source. | refuted; report correctly expects refusal | Honest capability boundary. |
| C-082 | Mandatory negative control goes red under a future cap/projector implementation. | Inspect expected refusal conditions. | confirmed_narrower | Structural negative is sound. |
| C-083 | `family_budget_exceeded: allocated=3/100` is a correct probability oracle for current source. | Exact schedule audit. | refuted | Blocking fixture defect. |
| C-084 | Property-removal control keeps fields and removes cap enforcement. | FWC-NEG-18/19. | confirmed as specification | Strong anti-marker test. |
| C-085 | Fixture uses live scope derivation, roots, heads, and chronology rather than author markers. | Algorithm steps 6/9/10; negative controls. | confirmed as future criterion | No live implementation. |
| C-086 | Artifact sketch is only a loose semantic note. | Count fixed names, schema versions, fields, enums, algorithms, refusals. | refuted | It functions as a de facto contract. |
| C-087 | Sketch creates a second confidence ledger. | Inspect anti-duplication and state ownership. | refuted | No second ledger proposed. |
| C-088 | Sketch creates a parent risk scope or family ordinal. | Inspect declaration/projection semantics. | refuted | Explicitly prohibited. |
| C-089 | Sketch weakens `design-problem` identity. | Scope derivation checks. | refuted | Identity preserved. |

---

## 8. Scope and standing claims

| ID | Claim | Verification method | Verdict |
| --- | --- | --- | --- |
| C-090 | Audited diff contains only three added Markdown files. | GitHub compare baseline to audited head. | confirmed |
| C-091 | Audited branch is 11 commits ahead and not behind baseline. | GitHub compare metadata. | confirmed |
| C-092 | No code, test, or existing document changed. | Per-file diff status. | confirmed |
| C-093 | Report appoints a new canonical owner. | Read frontmatter/handoff. | refuted | It points to the existing owner and disclaims appointment. |
| C-094 | Report freezes package placement or final schema. | Frontmatter says no; sketch supplies detailed placeholder names. | confirmed_narrower | No actual code placement, but contract hardening is material. |
| C-095 | `accepted_narrow_scope` accurately describes a mathematically sound package. | Formal audit. | refuted at audited head | Blocking source-sharpness error requires `NO_GO`/revision. |
| C-096 | Runtime capability is blocked. | GY-GAP2 and source search. | confirmed | Preserve. |
| C-097 | S0-K05 is respected. | Boundary table and projection disclaimers. | confirmed |
| C-098 | S0-K16 is respected. | Fixture/pass boundary and may-not-use language. | confirmed |
| C-099 | Candidate-band work remains allowed under limitation. | §§1.4, 4.8, 5, 9. | confirmed |
| C-100 | INT-R1 conditionality is silently discharged. | Compare all claim language. | refuted | Conditionality is consistently preserved. |

---

## 9. Ledger conclusion

Of the one hundred load-bearing and boundary claims audited:

- the fixed-family union theorem, exact event, owner reuse, conditionality, external transfer
  judgments, negative capability standing, and anti-duplication rules are strong;
- the adaptive theorem needs formal repair but its current “blocked” conclusion is safe;
- the repository and empirical census is largely accurate, aside from weak anchors and the
  proof-profile/instrument distinction; and
- the pinned-source `3 * delta` sharpness, `3/100` handoff, equal-third necessity, and corresponding
  fixture oracle are refuted.

The refuted arithmetic is load-bearing enough that the overall audit cannot be
`GO_WITH_REVISIONS`. It requires amendment of the research result before consolidation and before
INT-R9 may rely on its numeric conclusions.