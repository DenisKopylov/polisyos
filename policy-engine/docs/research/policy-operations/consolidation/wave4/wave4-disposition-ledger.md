---
title: Wave 4 — disposition ledger
status: delivered_consolidation
kind: research_consolidation_disposition_ledger
research_scope: [OPS-R14, PAO-R36, PAO-R4, S0-GAP-02]
repository_branch: research/wave4-consolidation
orientation_commit: 610e485569da8b5b13afd767ae52b29d3f2c8e95
documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
inspection_date: 2026-08-17
research_only: true
audit_finding_rows: 128
named_verifier_finding_rows: 20
amendment_disposition_totals:
  accepted: 115
  accepted_with_variation: 11
  declined_with_reason: 2
may_not_use_for:
  - ratification
  - production implementation authorization
  - package repair or mutation
  - final wire, schema, package, database, serialization, media type, or API contract
  - canonical owner, vendor, custodian, evaluator, signer, or institution appointment
  - authority grant
  - capability claim
  - permission to publish, sign, score, promote, or open a gate
  - claim that OPS-R15 is unblocked
  - automatic amendment of AGENTS.md, the pattern register, a plan, backlog, or system-design decision
---

# Wave 4 disposition ledger

## 1. Boundary and source discipline

This ledger **dispositions** evidence. It does not edit a package, repair a package, reopen an accepted finding, or ratify a proposition.

The audited defect text and the response text are on disjoint lines. The source keys below keep them separate; a row never uses a response-line location as evidence for the originating defect.

| Package | Line A — audited text and audit findings | Line B — terminal response and verification |
| --- | --- | --- |
| OPS-R14 | research `3a694212a`; audit `34c65a04e`; `audits/ops-r14-wave4/ops-r14-independent-audit.md` | amendment `83539ebf0`; amendment verification `0fe8fe6a0`; remediation `62de2c5fe`; terminal delta verification `915ed6031` |
| PAO-R36 | research `1bccc012b`; audit `9bbfd37a2`; `audits/pao-r36/pao-r36-independent-audit.md` | amendment `926326174`; terminal verification `47f0680f4` |
| PAO-R4 | research `a27c3da99`; audit `69182c079`; `audits/pao-r4/pao-r4-independent-audit.md` | amendment `0df03f35e`; terminal verification `93571fd3c` |
| S0-GAP-02 | research `a7c34cc40`; audit `3abbaf8c2`; `audits/s0-gap-02/s0-gap-02-independent-audit.md` | amendment `c14e3d435`; terminal verification `0c7ab71aa` |

`closed at consolidation` means the complete pinned census executed at consolidation level with positive and negative controls. It does **not** retroactively make a package the executing party. `route` means the evidence survives for a later owner or ratification act; it is not a package edit made here.

## 2. Count reconciliation

| Package | Audit rows | Ledger result re-derived from rows | Named verifier findings |
| --- | ---: | --- | ---: |
| OPS-R14 | 28 | 24 `accepted` · 3 `accepted_with_variation` · 1 `declined_with_reason` | 4 |
| PAO-R36 | 39 | 35 `accepted` · 3 `accepted_with_variation` · 1 `declined_with_reason` | 12 |
| PAO-R4 | 30 | 27 `accepted` · 3 `accepted_with_variation` · 0 declined | 1 |
| S0-GAP-02 | 31 | 29 `accepted` · 2 `accepted_with_variation` · 0 declined | 3 |
| **Total** | **128** | **115 accepted · 11 with variation · 2 declined** | **20** |

## 3. OPS-R14 — 28 audit findings

| Audit ID | Severity | Amendment-ledger disposition | Verification | Terminal consolidation state |
| --- | --- | --- | --- | --- |
| `OPS-R14-I-001` | minor | `accepted` | Confirmed: all-source and Python denominators are stated separately. | **closed** — denominator ambiguity removed. |
| `OPS-R14-I-002` | minor | `accepted_with_variation` | Amendment verifier opened `AV-B01`; remediation verifier confirmed the package no longer claims it executed the walk. | **closed** — census facts reproduced by consolidation; package attribution remains `institutionally_supplied`. |
| `OPS-R14-I-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — worker processing-lease renewal is not authority renewal. |
| `OPS-R14-II-001` | material | `accepted` | Confirmed bounded transfer from procurement sources. | **closed** — durable-file lessons retained; instrument-specific authority predicates remain external. |
| `OPS-R14-II-002` | minor | `declined_with_reason` | Amendment verifier opened `AV-N01` because currentness language survived; remediation verifier confirmed the currentness refusal landed. | **decline confirmed; response gap closed** — no fresh link retrieval was invented and currentness is `not_established`. |
| `OPS-R14-II-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — transfer/non-transfer columns remain bounded. |
| `OPS-R14-III-001` | blocking | `accepted_with_variation` | Confirmed across all terminal artifacts. | **closed** — three standing axes exist: research, capability, first-public-signature gate. |
| `OPS-R14-III-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — seven operational/institutional absences remain explicit. |
| `OPS-R14-III-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — research architecture grants no implementation, publication, signing, or gate authority. |
| `OPS-R14-III-004` | commendation | `accepted` | Confirmed preserved and strengthened under P37. | **preserved** — class-specific acknowledgement, loss, RPO/RTO, and restoration stay separate. |
| `OPS-R14-IV-001` | material | `accepted` | Confirmed: runbook presence is no longer recovery closeout evidence. | **closed** — taxonomy defect registered as `OPS-R14-ACCEPTANCE-001`. |
| `OPS-R14-IV-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — green documentation/tabletop rows do not establish exercised recovery. |
| `OPS-R14-V-001` | material | `accepted` | Confirmed: WD-05A adds due-event delivery reconciliation and durable gap evidence. | **closed at research-contract level**; runtime chain remains absent/unallocated. |
| `OPS-R14-V-002` | minor | `accepted` | Confirmed narrowed. | **closed** — local intent alone is insufficient; a competent unilateral exercise remains possible only when the instrument proves it. |
| `OPS-R14-V-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — six watched-dependency families remain distinct. |
| `OPS-R14-V-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — legal hold is an orthogonal disposal override, not validity or currentness. |
| `OPS-R14-VI-001` | material | `accepted_with_variation` | **Disputed in part.** `F-14B` was verified; `AV-B02` remained `NOT_CLOSED` because `F-14A` measured content agreement rather than provenance independence. | **split disposition** — `F-14B` preserved; `F-14A` withdrawn by carried architect ruling, with a genuinely disjoint-custody record as the condition for any future positive. No “strengthen F-14A” round may be routed. |
| `OPS-R14-VI-002` | material | `accepted` | Confirmed: common-mode, authenticated-time rollback, and parser/canonicalization attacks added. | **closed at research-contract level**. |
| `OPS-R14-VI-003` | minor | `accepted` | Confirmed: real-path identity and permissive-stub substitution checks added. | **closed at research-contract level**. |
| `OPS-R14-VI-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — original fixtures remain; denominator expanded without weakening them. |
| `OPS-R14-VI-005` | commendation | `accepted` | Confirmed preserved. | **preserved** — DE-01–DE-10 and Phase-A non-circularity remain controlling. |
| `OPS-R14-VII-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — PV-K02 failure-state discipline remains complete. |
| `OPS-R14-VII-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — GY-N12 is consumed as the sole currentness/epoch owner, not duplicated. |
| `OPS-R14-VIII-001` | commendation | `accepted` | Confirmed exactly in terminal seam summaries. | **preserved** — F11 closes only by `RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`. |
| `OPS-R14-IX-001` | material | `accepted` | Confirmed. | **closed** — noncanonical “implemented as documentation artifacts only” label removed. |
| `OPS-R14-IX-002` | minor | `accepted` | Confirmed. | **closed** — GY-N12 is `contract_only` only at plan-contract layer and `absent/unallocated` at runtime. |
| `OPS-R14-IX-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — prerequisite-safe maturity-label discipline holds. |
| `OPS-R14-X-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — prohibitions and research-only boundary remain intact. |

### OPS-R14 named verifier findings

| Verifier ID | Origin | Verification disposition | Terminal consolidation state |
| --- | --- | --- | --- |
| `OPS-R14-AV-B01` | amendment verification | Blocking census-attribution defect; remediation claimed closure; delta verifier confirmed closure. | **closed** — package no longer claims execution; consolidation reproduced the census. |
| `OPS-R14-AV-B02` | amendment verification | Blocking F-14 positive-route defect; remediation claimed closure; delta verifier disputed it. | **dispositioned by carried ruling** — withdraw `F-14A`; preserve `F-14B`; route disjoint custody as the only return condition. |
| `OPS-R14-AV-N01` | amendment verification | Non-blocking currentness overclaim; remediation and delta verifier confirmed closure. | **closed**. |
| `OPS-R14-DV-N01` | remediation delta verification | Author-side final branch readback was not evidenced. | **recorded, not repaired here** — delivery/readback evidence is a process obligation; it does not reopen package research findings. |

## 4. PAO-R36 — 39 audit findings

| Audit ID | Severity | Amendment-ledger disposition | Verification | Terminal consolidation state |
| --- | --- | --- | --- | --- |
| `PAO-R36-I-001` | material | `declined_with_reason` | Verifier confirmed the audit's indexed 47/203/246 was not a complete denominator; consolidation independently reproduced 48/215/260. | **decline confirmed** — architect adjudication honored. |
| `PAO-R36-I-002` | minor | `accepted_with_variation` | Confirmed. | **closed** — units and all-source/Python denominators are explicit. |
| `PAO-R36-I-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — structural owner/declaration/line-count conclusions remain bounded. |
| `PAO-R36-I-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — generic cache/subscriber tokens are not correction capability. |
| `PAO-R36-I-005` | commendation | `accepted_with_variation` | Verifier left the complete-walk execution gap; consolidation reproduced all zeroes but found two package-level attribution overclaims. | **facts closed at consolidation; package correction routed** — `amendment-ledger.md:58` and `:107` must name the executing party and holder-relative P37 label. |
| `PAO-R36-II-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — statistical-revision transfer remains bounded. |
| `PAO-R36-II-002` | minor | `accepted` | Confirmed narrowed. | **closed** — accessibility attaches only to otherwise-required notice/status/recourse. |
| `PAO-R36-II-003` | minor | `accepted` | Confirmed. | **closed** — COPE source pinned to Version 3, August 2025. |
| `PAO-R36-II-004` | minor | `accepted` | Confirmed narrowed. | **closed** — Regulation No 1 supports enumeration/communication, not semantic identity. |
| `PAO-R36-II-005` | commendation | `accepted` | Confirmed preserved. | **preserved** — external sources create no direct PolicyOS duty or legal-sufficiency claim. |
| `PAO-R36-III-001` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — one controlling order proves the notice/fence before current authority. |
| `PAO-R36-III-002` | blocking | `accepted` | Confirmed. | **closed** — `Complete(R_gate)` precedes declaration; `R_post` adds it explicitly. |
| `PAO-R36-III-003` | blocking | `accepted` | Confirmed. | **closed** — receipt obligation and provenance freeze at admission; unknown defaults synchronous. |
| `PAO-R36-III-004` | material | `accepted` | Confirmed. | **closed** — observer labels bind the complete correction tuple. |
| `PAO-R36-III-005` | material | `accepted` | Confirmed. | **closed** — strict append order is independent of display timestamps and backdating. |
| `PAO-R36-III-006` | commendation | `accepted` | Confirmed preserved. | **preserved** — two-boundary construction remains controlling. |
| `PAO-R36-III-007` | commendation | `accepted` | Confirmed preserved. | **preserved** — three safe mixed-state labels remain exclusive. |
| `PAO-R36-IV-001` | material | `accepted` | Confirmed. | **closed** — surface/cache snapshots bind controlled generation and restart on drift. |
| `PAO-R36-IV-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — unknown external copies remain exclusions; no universal internet-cleared claim. |
| `PAO-R36-IV-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — member/count/cutoff/exclusion discipline is strengthened, not widened. |
| `PAO-R36-V-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — risk-increasing correction case remains decidable without legal sufficiency. |
| `PAO-R36-V-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — predecessor stays historically retrievable without automatic retroactivity. |
| `PAO-R36-V-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — revoked-key case consumes terminal INT-R7 dimensions without local crypto design. |
| `PAO-R36-VI-001` | material | `accepted` | Confirmed. | **closed** — ambiguous/disjunctive cases split into deterministic worlds. |
| `PAO-R36-VI-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — F13 exact `as_of` inversions remain. |
| `PAO-R36-VI-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — F16 removes one live member while green markers remain. |
| `PAO-R36-VI-004` | material | `accepted` | Confirmed. | **closed** — serialized stale-base correction attack added. |
| `PAO-R36-VI-005` | material | `accepted` | Confirmed. | **closed** — receipts bind exact correction/snapshot/generation/predicate tuple and reject replay. |
| `PAO-R36-VI-006` | commendation | `accepted` | Confirmed preserved. | **preserved** — two-direction laundering attack remains exact. |
| `PAO-R36-VII-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — non-erasure/currentness law remains behaviorally detectable. |
| `PAO-R36-VII-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — PV-K04 continues to bind correction projection. |
| `PAO-R36-VII-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — existing evolution/projection/currentness owners remain controlling. |
| `PAO-R36-VIII-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — OPS-R14 seam is not re-adjudicated. |
| `PAO-R36-VIII-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — INT-R6 remains an interface dependency; no parity mechanism is smuggled in. |
| `PAO-R36-VIII-003` | minor | `accepted` | Confirmed. | **closed** — final INT-R7 claims read through terminal Section 18. |
| `PAO-R36-IX-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — generic public-export producer/HTTP consumer relation is `bridge_missing`; correction specialization remains absent. |
| `PAO-R36-IX-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — correction notice/feed/subscriber/cache/archive/E2E chains are `absent/unallocated`. |
| `PAO-R36-X-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — research-only prohibitions remain intact. |
| `PAO-R36-X-002` | commendation | `accepted_with_variation` | Confirmed substantively; consolidation found the one-field standing shape remains noncanonical. | **research result preserved; standing-shape correction routed to AGENTS.md**. |

### PAO-R36 named verifier findings

| Verifier ID | Class | Terminal consolidation state |
| --- | --- | --- |
| `PAO-R36-AMV-I-001` | material gap | **census facts closed at consolidation; attribution route remains** at the two live amendment-ledger sites. |
| `PAO-R36-AMV-I-002` | commendation | **preserved** — exact branch/file arithmetic and both `+267` derivations reconcile. |
| `PAO-R36-AMV-III-001` | commendation | **preserved** — one controlling order closes both forbidden crash windows. |
| `PAO-R36-AMV-III-002` | commendation | **preserved** — `R_gate`/`R_post` is non-circular. |
| `PAO-R36-AMV-III-003` | commendation | **preserved** — receipt obligation is frozen and the async escape is closed. |
| `PAO-R36-AMV-IV-001` | commendation | **preserved** — registered five-label P37 table and behavioral probe conform. |
| `PAO-R36-AMV-V-001` | commendation | **preserved** — observer state, generations, and receipts bind semantic identity. |
| `PAO-R36-AMV-VI-001` | commendation | **preserved** — former conditional falsifiers are deterministic single worlds. |
| `PAO-R36-AMV-VI-002` | commendation | **preserved** — F18 detects serialized stale-base loss. |
| `PAO-R36-AMV-VI-003` | commendation | **preserved** — F22 rejects wrong/staged/stale tuple despite green labels. |
| `PAO-R36-AMV-VII-001` | commendation | **preserved** — inspected ratified kernels remain conformed. |
| `PAO-R36-AMV-X-001` | commendation | **preserved** — prohibitions and capability honesty survive. |

## 5. PAO-R4 — 30 audit findings

| Audit ID | Severity | Amendment-ledger disposition | Verification | Terminal consolidation state |
| --- | --- | --- | --- | --- |
| `PAO-R4-I-001` | material | `accepted` | Confirmed: `anonymi` is seven all-source files and six Python files. | **closed** — denominator corrected; token presence still proves no firewall property. |
| `PAO-R4-I-002` | material | `accepted` | Verifier explicitly did not freshly recompute the full tree; consolidation reproduced the census and found three live attribution overclaims. | **facts closed at consolidation; package correction routed** to `orientation-ledger.md:149`, `:199`, and `amendment-delivery-readback.md:120`. |
| `PAO-R4-I-003` | commendation | `accepted` | Preserved, but its zero-language analogue was not regraded by the verifier. | **source-shape commendation preserved; holder-relative zero attribution routed with I-002**. |
| `PAO-R4-II-001` | material | `accepted` | Confirmed narrowed. | **closed** — “not weaker” is a bounded project rule, not universal external law. |
| `PAO-R4-II-002` | material | `accepted` | Confirmed. | **closed** — Canadian and OMB sources are pinned and currentness bounded. |
| `PAO-R4-II-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — source transfer limits remain explicit. |
| `PAO-R4-II-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — sources support bounded analogies, not direct authority. |
| `PAO-R4-III-001` | blocking | `accepted_with_variation` | Confirmed under the architect-narrowed §4.2/§4.3 contract. | **closed as narrowed** — firewall binds authority to determine, never executability. |
| `PAO-R4-III-002` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — basis/history completeness and material contribution are fail-closed predicates. |
| `PAO-R4-III-003` | material | `accepted` | Confirmed. | **closed** — singleton/deterministic empirical artifacts are handled separately. |
| `PAO-R4-III-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — aggregate empirical evidence remains non-individual authority. |
| `PAO-R4-IV-001` | material | `accepted` | Confirmed. | **closed** — export-context and use-context gates are explicit and distinct. |
| `PAO-R4-IV-002` | material | `accepted` | Confirmed. | **closed** — any positive is bounded to independently reconciled governed records. |
| `PAO-R4-IV-003` | material | `accepted_with_variation` | Confirmed narrowed. | **closed** — voluntary reports support incidents/lower bounds/samples, never complete non-use. |
| `PAO-R4-IV-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — four-location detection partition remains. |
| `PAO-R4-IV-005` | commendation | `accepted` | Confirmed preserved. | **preserved** — voluntary silence cannot prove non-use. |
| `PAO-R4-V-001` | material | `accepted_with_variation` | Confirmed under the architect-narrowed contract. | **closed as narrowed** — executability is not the firewall property; authority/use effect is. |
| `PAO-R4-V-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — candidate-band rule use grants no PolicyOS authority. |
| `PAO-R4-VI-001` | material | `accepted` | Confirmed. | **closed** — consultation includes manual/cognitive and routing effects, not only machine calls. |
| `PAO-R4-VI-002` | material | `accepted` | Confirmed. | **closed** — logs establish consultation only within a bounded instrumented denominator, not causal materiality. |
| `PAO-R4-VI-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — returning-evidence intake remains required and independently reconciled. |
| `PAO-R4-VII-001` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — F-01 exercises planning-to-eligibility drift through the real gate property. |
| `PAO-R4-VII-002` | material | `accepted` | Confirmed. | **closed** — missing/ambiguous basis, purpose, history, and consumer evidence attacks added. |
| `PAO-R4-VII-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — four original attack classes remain. |
| `PAO-R4-VIII-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — PV-K04 projection monotonicity remains controlling. |
| `PAO-R4-VIII-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — kernel/anti-role boundaries remain explicit. |
| `PAO-R4-IX-001` | material | `accepted` | Confirmed: `public_export.py` adjacency does not appoint the canonical policy-to-case chokepoint. | **closed as research finding; owner decision remains open** — no owner exists yet. |
| `PAO-R4-IX-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — capability chain remains `absent/unallocated`, not a downstream missing-state label. |
| `PAO-R4-X-001` | minor | `accepted` | Confirmed by amendment readback and verifier. | **closed**. |
| `PAO-R4-X-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — sibling isolation and prohibitions remain intact. |

### PAO-R4 named verifier finding

| Verifier ID | Origin | Verification disposition | Terminal consolidation state |
| --- | --- | --- | --- |
| `PAO-R4-AMV-I-001` | amendment verification | Material, non-blocking: raw-tree census not freshly recomputed; verifier nevertheless left “settled true zeroes” standing. | **facts closed at consolidation; attribution defect survives and is routed to the three exact sites**. This is the analogue OPS-R14's verifier caught and PAO-R4's verifier missed. |

## 6. S0-GAP-02 — 31 audit findings

| Audit ID | Severity | Amendment-ledger disposition | Verification | Terminal consolidation state |
| --- | --- | --- | --- | --- |
| `S0-GAP-02-I-001` | material | `accepted` | Verifier could not execute the complete token walk; consolidation reproduced the counts. | **closed at consolidation** — package already attributes the census to the architect and does not use token zeroes as universal semantic proof. |
| `S0-GAP-02-I-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — connector/index absence remains inadmissible as a denominator. |
| `S0-GAP-02-I-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — bounded three-owner semantic sample remains evidence, not a universal theorem. |
| `S0-GAP-02-I-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — prior-art census remains bounded. |
| `S0-GAP-02-I-005` | material | `accepted` | Confirmed narrowed. | **closed** — package does not claim no independent evaluator exists anywhere under another name. |
| `S0-GAP-02-II-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — external sources are bounded and non-authoritative for implementation. |
| `S0-GAP-02-II-002` | minor | `accepted` | Confirmed. | **closed** — HKUST reference stabilized. |
| `S0-GAP-02-III-001` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — shared substrate requires constructed `AnswerNeutral(z,f)` evidence and poisoned-helper probes. |
| `S0-GAP-02-III-002` | material | `accepted_with_variation` | Verifier commended the six-way distinctions and found no widening of the positive set. | **substance preserved; label shape routed** — registered five remain labels; machine observation, attestation, and institutional acceptance become required sub-annotations. |
| `S0-GAP-02-III-003` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — discriminator existence, liveness, removal, and neutralization are all required. |
| `S0-GAP-02-III-004` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — specification-side assurance and bad-axiom falsifiers added. |
| `S0-GAP-02-III-005` | commendation | `accepted` | Confirmed preserved. | **preserved** — shared input is distinguished from shared answer production. |
| `S0-GAP-02-III-006` | commendation | `accepted` | Confirmed preserved. | **preserved** — independent channels form a conjunction, not a vote. |
| `S0-GAP-02-IV-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — same-code control `C` is diagnostic and absent from every verification claim. |
| `S0-GAP-02-V-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — seeded shared product-reducer fault yields `ARCHITECTURE_FALSIFIED`. |
| `S0-GAP-02-V-002` | material | `accepted` | Confirmed. | **closed at research-contract level** — mutation generator/validator/evaluators require separate provenance. |
| `S0-GAP-02-V-003` | material | `accepted` | Confirmed. | **closed at research-contract level** — reviewer unanimity without proficiency cannot establish correctness. |
| `S0-GAP-02-V-004` | material | `accepted` | Confirmed. | **closed at research-contract level** — transitive provenance and common private ancestors are disclosed and tested. |
| `S0-GAP-02-VI-001` | blocking | `accepted` | Confirmed. | **closed at research-contract level** — finite-domain PDL rejects tautological/catch-all bundles and blocks unknown proof status. |
| `S0-GAP-02-VI-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — finite alternatives remain explicit and decidable. |
| `S0-GAP-02-VII-001` | material | `accepted` | Confirmed. | **closed at research-contract level** — `B`→`O_v` requires independent derivation or dual control. |
| `S0-GAP-02-VII-002` | material | `accepted` | Confirmed. | **closed at research-contract level** — storage/network/key access heads require independent reconciliation. |
| `S0-GAP-02-VII-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — challenge, correction, and supersession history is append-only. |
| `S0-GAP-02-VII-004` | commendation | `accepted` | Confirmed preserved. | **preserved** — silent oracle/evaluator change is forbidden. |
| `S0-GAP-02-VIII-001` | commendation | `accepted_with_variation` | Verifier confirmed the architect-directed placement. | **preserved as narrowed** — `SPECIFICATION_ASSURANCE_NOT_ESTABLISHED` is governed negative completion under `INT-K08`, not a fourth outcome. |
| `S0-GAP-02-VIII-002` | commendation | `accepted` | Confirmed preserved. | **preserved** — P27/P28 owner-first rule retains the S0-K14 verification-independence exception. |
| `S0-GAP-02-IX-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — capability remains absent/unallocated; downstream missing-state labels are not borrowed. |
| `S0-GAP-02-IX-002` | material | `accepted` | Confirmed. | **closed at research-contract level** — blocking challenge closure is required before claim rendering. |
| `S0-GAP-02-X-001` | commendation | `accepted` | Confirmed preserved. | **preserved** — research-only isolation and prohibitions hold. |
| `S0-GAP-02-X-002` | material | `accepted` | Confirmed substantively; verifier separately observed standing-shape ambiguity. | **research rationale closed; standing-shape route remains** to the three-axis AGENTS.md rule. |
| `S0-GAP-02-X-003` | commendation | `accepted` | Confirmed preserved. | **preserved** — byte identity and provenance independence remain distinct properties. |

### S0-GAP-02 named verifier findings

| Verifier ID | Origin | Verification disposition | Terminal consolidation state |
| --- | --- | --- | --- |
| `S0-GAP-02-AV-P37-001` | amendment verification | Commendation: six-way crosswalk preserves real distinctions without widening its stated positive set. | **routed, not adopted as labels** — retain the registered five; require the three distinctions as sub-annotations. |
| `S0-GAP-02-AV-I-001` | amendment verification | Non-blocking complete-census execution gap. | **closed at consolidation** with holder-relative attribution preserved. |
| `S0-GAP-02-AV-S-001` | amendment verification | Non-blocking standing-shape observation. | **routed to AGENTS.md** with OPS-R14's three fields as the reference shape. |

## 7. Cross-package analogue sweep

| Analogue | OPS-R14 | PAO-R36 | PAO-R4 | S0-GAP-02 | Consolidation disposition |
| --- | --- | --- | --- | --- | --- |
| Package claims a complete census it did not execute | Verifier graded blocking and forced removal. | Verifier recorded material gap; two “architect supplied, therefore settled” sites survive. | Verifier recorded material gap but left three “true zero” sites standing. | Verifier recorded the execution gap; package already names architect supply and does not use token counts as universal semantic absence. | **One defect, two live phrasing families, five exact correction sites.** Facts are closed only at consolidation level. |
| Added condition preserves a positive without constructing the named property | `F-14A`: content agreement offered for provenance independence. | No surviving analogue found. | No surviving analogue found. | `machine_observed`: positive eligibility depended on a declared condition. | **New P37 application rule routed beside P37; no conditional positive lookup.** |
| One standing field collapses research, capability, and gate state | Three fields; defect closed. | One field. | One field publishes `GO_WITH_REVISIONS` while capability is absent. | One field; verifier flagged shape. | **OPS-R14 three-axis shape is the reference; route to AGENTS.md.** |
| Owner-first handoff shape | Typed ENG/INST/RES tables. | Owner-first integration map plus four dependency declarations. | Typed tables. | Typed tables. | **Record format divergence; preserve owner-first substance and normalize routing at consolidation only.** |

No other cross-package analogue was found in which one verifier confirmed a defect and another package retained the same defect unremarked.

## 8. Non-movement confirmation

The inventory does not reopen an accepted finding. It does not promote a capability, appoint an owner, open a gate, authorize a signature, or unblock OPS-R15. Every package's complete capability chain remains `absent/unallocated`, with the same prerequisite-based refusal to misuse `contract_only`, `producer_missing`, `bridge_missing`, or `verification_missing`.