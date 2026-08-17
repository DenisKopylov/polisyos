---
title: Wave 4 — orientation audit record
status: delivered_consolidation_audit
kind: research_consolidation_orientation_audit
research_scope: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
repository_branch: research/wave4-consolidation
requested_orientation_commit: 610e485568e5b0b70bfa3aa6b2eb1e63cbf6a0c1
resolved_orientation_commit: 610e485569da8b5b13afd767ae52b29d3f2c8e95
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
inspection_date: 2026-08-17
research_only: true
checks_complete_except:
  - exact_terminal_occurrence_recount_for_p37_labels
may_not_use_for:
  - ratification
  - package repair or mutation
  - production implementation authorization
  - capability claim
  - owner appointment
  - permission to publish, sign, score, promote, or open a gate
  - claim that OPS-R15 is unblocked
  - automatic amendment of AGENTS.md, the pattern register, a plan, backlog, or system-design decision
---

# Wave 4 orientation audit record

## 1. Method and evidence boundary

The orientation pack is evidence, not authority. Set-level facts were re-derived from exact refs, exact commit comparisons, complete audit registers, terminal response manifests, independent-verification manifests, and the controlled census record at the documentation pin.

One requested check remains explicitly **not established**: an independent exact occurrence recount of all seven P37-related label strings over all 44 terminal Markdown files. The connector permits exact file reads but not one bulk exact-ref content materialization; using indexed search would violate P35. The pack's frequency table is therefore recorded as architect-supplied and is not restated as this consolidator's measurement. Vocabulary membership and positive-eligibility semantics were independently checked.

## 2. Input-pin reconciliation

### Divergence `OA-D01` — requested orientation SHA does not exist

The instruction supplied:

`610e485568e5b0b70bfa3aa6b2eb1e63cbf6a0c1`

The repository has no commit at that identity. The branch and orientation pack resolve to:

`610e485569da8b5b13afd767ae52b29d3f2c8e95`

The difference is not cosmetic: the supplied SHA differs after `610e48556`. All checks in this record use the resolved exact commit. The orientation pack blob is `3777954652c2ee3efe68cec8d5e15bd226bd719a`.

## 3. Structural topology — no divergence

### 3.1 Audit line contains research

| Package | Research → audit comparison | Re-derived result |
| --- | --- | --- |
| OPS-R14 | `3a694212a` → `34c65a04e` | audit is 7 commits ahead, merge base exactly research; seven audit Markdown files added |
| PAO-R36 | `1bccc012b` → `9bbfd37a2` | audit is 7 commits ahead, merge base exactly research; seven audit Markdown files added |
| PAO-R4 | `a27c3da99` → `69182c079` | audit is 7 commits ahead, merge base exactly research; seven audit Markdown files added |
| S0-GAP-02 | `a7c34cc40` → `3abbaf8c2` | audit is 11 commits ahead, merge base exactly research; seven audit Markdown files added |

### 3.2 Amendment line excludes audit

| Package | Audit → amendment comparison | Re-derived result |
| --- | --- | --- |
| OPS-R14 | `34c65a04e` ↔ `83539ebf0` | diverged; amendment merge base is research; amendment is 7 audit commits behind |
| PAO-R36 | `9bbfd37a2` ↔ `926326174` | diverged; amendment merge base is research; amendment is 7 audit commits behind |
| PAO-R4 | `69182c079` ↔ `0df03f35e` | diverged; amendment merge base is research; amendment is 7 audit commits behind |
| S0-GAP-02 | `3abbaf8c2` ↔ `c14e3d435` | diverged; amendment merge base is research; amendment is 11 audit commits behind |

Every verification descends from its amendment; OPS-R14 remediation descends from its amendment and the delta verification descends from remediation. No terminal response ref contains the original independent-audit directory. The structural trap is exactly as described.

### 3.3 Path collision — no divergence

Both lines modify the same package paths. Audit findings cite the pre-amendment line-A text; terminal state is on line B. This consolidation keeps defect and response anchors separate and does not translate line numbers across branches.

## 4. Terminal file counts and line totals — no divergence

The pack's terminal totals include the response-line package files plus the terminal independent-verification file(s), not only the package directory.

| Package | Re-derived arithmetic | Terminal total | Pack result |
| --- | --- | ---: | --- |
| OPS-R14 | 10 package Markdown files / 2,986 lines + delta verification 371 | **11 / 3,357** | exact |
| PAO-R36 | 8 amended package files / 2,564 lines + two verification files / 687 lines | **10 / 3,251** | exact |
| PAO-R4 | complete package 10 files / 2,397 lines + verification 484 | **11 / 2,881** | exact |
| S0-GAP-02 | audited package 3,153 + amendment net `1,767 - 1,093 = +674` → 11 files / 3,827 lines; verification 374 | **12 / 4,201** | exact |

### PAO-R36 shrink/expansion explanation

The two shrinking artifacts are not unexplained deletions:

- the primary report shrinks `684 → 509` because contradictory/repeated order and completeness text is replaced by one controlling transaction order and bounded summaries;
- the ordered contract shrinks `538 → 480` because circular/duplicated gate language is replaced by `R_gate`/`R_post`, frozen obligation classes, exact generation binding, and one canonical order; and
- the falsifier suite expands `374 → 698` because conditional worlds are split and F18–F22 add stale-base, receipt-replay, event-order, generation-drift, and full-tuple attacks.

No source, workflow, binary, staging, transport, AGENTS.md, or pattern-register path appears in any response-line delta.

## 5. Audit finding totals and blockers — no divergence

| Package | Re-derived severity arithmetic | Pack result |
| --- | --- | --- |
| OPS-R14 | 1 blocking + 6 material + 6 minor + 15 commendation = **28** | exact |
| PAO-R36 | 3 blocking + 7 material + 5 minor + 24 commendation = **39** | exact |
| PAO-R4 | 3 blocking + 13 material + 1 minor + 13 commendation = **30** | exact |
| S0-GAP-02 | 4 blocking + 10 material + 1 minor + 16 commendation = **31** | exact |

## 6. Amendment-ledger dispositions — material divergence

### Divergence `OA-D02` — every pack disposition summary is arithmetically wrong

The ledger rows, not summary prose, control.

| Package | Pack statement | Re-derived from every ledger row | Difference |
| --- | --- | --- | --- |
| OPS-R14 | `25 accepted / 4 with-variation` | **24 accepted / 3 with-variation / 1 declined** | Pack overstates accepted by 1 and variations by 1; omits the declined row `OPS-R14-II-002`. |
| PAO-R36 | `36 / 4 / 3 rejected / 2 declined / 1 superseded` | **35 accepted / 3 with-variation / 1 declined** | Pack introduces disposition classes not used by the ledger and sums to 46 against 39 findings. |
| PAO-R4 | `29 / 5` | **27 accepted / 3 with-variation / 0 declined** | Pack sums to 34 against 30 findings. |
| S0-GAP-02 | `31 / 4` | **29 accepted / 2 with-variation / 0 declined** | Pack sums to 35 against 31 findings. |
| **Wave** | not stated correctly | **115 accepted / 11 with-variation / 2 declined = 128** | Correct complete denominator. |

The disposition ledger in this consolidation uses the re-derived counts.

## 7. Verification verdict state — no divergence

| Package | Terminal verification state |
| --- | --- |
| OPS-R14 | amendment verification `NO_GO` with two blocking and one non-blocking finding; remediation delta verification remains `NO_GO` because `AV-B02` is `NOT_CLOSED`, with one separate non-blocking delivery finding |
| PAO-R36 | `CONFORMS_WITH_GAPS`, zero blockers, one material census-execution gap, eleven commendations |
| PAO-R4 | `CONFORMS_WITH_GAPS`, zero blockers, one material census-execution gap |
| S0-GAP-02 | `CONFORMS_WITH_GAPS`, zero blockers; one census gap and one standing-shape observation, plus a P37 commendation |

The common tree-walk limitation is closed only at consolidation level. OPS-R14's terminal `NO_GO` is instead driven by F-14A's provenance-measurement defect.

## 8. Standing fields

| Package | Pack claim | Re-derived result | Disposition |
| --- | --- | --- | --- |
| OPS-R14 | three fields in 11/11 terminal files | **11/11** carry `research_standing`, `capability_standing`, `gate_standing` | no divergence |
| PAO-R36 | `result_standing` in 8 files | **8/10 terminal files**; the two verification records use verifier verdict fields | no divergence |
| PAO-R4 | `result_standing: GO_WITH_REVISIONS` in 7 files | **7/11 terminal files**; receipts and verifier do not carry the field | no divergence |
| S0-GAP-02 | `result_standing` in 12 files | **11/12 terminal files**; all eleven amended artifacts carry it, the independent verification uses `result: CONFORMS_WITH_GAPS` instead | **divergence `OA-D03` — pack overstates by one** |

The semantic conclusion remains: OPS-R14's three-axis shape is the only shape that directly separates research acceptance, runtime capability, and first-public-signature permission.

## 9. P37 vocabulary and frequencies

### 9.1 Vocabulary membership — independently confirmed

- OPS-R14 uses the registered five and has one complete 48-predicate register.
- PAO-R36 uses the registered five in its normative predicate snapshot; no sixth label was found by its verifier.
- PAO-R4 uses the registered five; its verifier found no sixth label.
- S0-GAP-02 uses `recomputed`, `machine_observed`, `independently_reconciled`, `attested`, `institutionally_accepted`, and `not_established`; its verifier supplies the lossless crosswalk and confirms the non-positive set does not widen.

### 9.2 Exact terminal occurrence frequencies — not independently established

The pack reports:

| Package | recomputed | independently_reconciled | consumer_asserted | institutionally_supplied | not_established | machine_observed | institutionally_accepted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OPS-R14 | 37 | 18 | 6 | 42 | 47 | 0 | 0 |
| PAO-R36 | 47 | 53 | 12 | 12 | 19 | 0 | 0 |
| PAO-R4 | 16 | 19 | 12 | 11 | 69 | 0 | 0 |
| S0-GAP-02 | 30 | 20 | 3 | 3 | 101 | 11 | 15 |

This consolidator does **not** adopt those tuples as independently re-derived. Exact file reads and manifests were available, but no complete exact-ref bulk text materialization was available for a scripted occurrence walk, and indexed search is prohibited by P35. The frequencies therefore remain `institutionally_supplied` relative to this consolidation record.

### Divergence `OA-D04` — provenance, not a demonstrated numeric contradiction

The orientation pack labels every set-level number as recomputed. For the frequency table, that provenance is not reproducible in this consolidator's environment. No contradictory frequency was found; the exact tuples are **not established here**. What would settle the check is a retained script/output over the 44-file terminal manifest with file identities and both the searched labels and exact occurrence totals.

## 10. Census values and controls — no divergence

The controlled source walk at `109ba3f44`, path denominator `policy-engine/src`, fixed case-sensitive strings, binary excluded, reproduces the thirteen tokens in both all-source and Python denominators. The positive controls and negative control behave as declared. All six claimed zeroes reproduce; `legal_hold` is `2/7/8`, not the audit's `2/4/5`.

The only correction is attribution: consolidation is the executing holder; packages are not.

## 11. Five live census-attribution sites — no divergence in site inventory

The two phrasing families and five sites reproduce exactly:

| Family | Site |
| --- | --- |
| “settled/true zero/established absence” | PAO-R4 `orientation-ledger.md:149`, `orientation-ledger.md:199`, `amendment-delivery-readback.md:120` |
| “settled because architect supplied a walk” | PAO-R36 `amendment-ledger.md:58`, `amendment-ledger.md:107` |

### Qualification `OA-Q01` — capability absence does not depend solely on lexical zeroes

The pack says PAO-R4's negative capability conclusion “rests on” the zeroes. The terminal handoff also grounds `absent/unallocated` in the absence of an admitted typed chain, producer, persisted artifact, bridge, consumer, verification, and owner. The zeroes strengthen the orientation but are not the sole decisive predicate. Therefore the route corrects attribution while preserving the capability conclusion.

The same qualification applies to PAO-R36: zero correction-specific tokens strengthen but do not alone establish the absent/unallocated chain.

## 12. Agenda totals and shape — no divergence

The complete typed tables reproduce **27 engineering, 21 institutional, and 19 further-research** items. PAO-R36 uses an owner-first map plus four dependency declarations rather than typed tables. The routing map preserves that source shape and supplies a separate normalized reverse index.

No item requires a new theory result before the first milestone. INT-R6 is genuinely unresearched but blocks only authoritative multilingual parity; the fail-closed `not_established` result remains available.

## 13. Seam and non-movement — no divergence

The terminal OPS-R14 delta verification enumerates nine exact F11 summaries across eight artifacts. Every summary uses:

`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`

No RP-10-alone closure survives.

The following also remain unchanged:

- outcome vocabulary: three elements;
- `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED`: INT-K08 negative completion, not a fourth outcome;
- INT-wave §8 constitutional trigger: armed and unactivated;
- no accepted finding reopened;
- no capability, owner, gate, publication/signing permission, or OPS-R15 unblock promoted;
- `PAO-R36-I-001` declined on the correct 48/215/260 result;
- PAO-R4-III-001 narrowed to authority-to-determine, never executability; and
- S0-GAP-02 INT-K08 placement preserved.

## 14. P38 registration deficit — no divergence

At `109ba3f44`, `AGENTS.md` and `policy-design-case-failure-patterns.md` stop at P37. Later GY and Atlas plan text cites and defines P38. P38 is therefore an outstanding registration item and is not cited as registered by this consolidation.

## 15. Divergence summary

| ID | Result |
| --- | --- |
| `OA-D01` | Requested orientation SHA is invalid; exact pack commit is `610e485569da8b5b13afd767ae52b29d3f2c8e95`. |
| `OA-D02` | All four amendment-disposition summaries are wrong; correct wave total is 115 accepted, 11 with variation, 2 declined. |
| `OA-D03` | S0-GAP-02 has `result_standing` in 11 of 12 terminal files, not 12. |
| `OA-D04` | Exact P37 label-frequency tuples were not independently re-derived; pack values remain institutionally supplied relative to this consolidator. |
| `OA-Q01` | PAO-R4/PAO-R36 absent capability conclusions do not rest solely on lexical zeroes; attribution correction does not reopen those conclusions. |

All other commissioned orientation checks found **no divergence**.