---
title: PAO-R36 - Orientation and Repository Evidence Ledger
research_id: PAO-R36
status: amended_research
result_standing: accepted_narrow_scope
audit_disposition_of_submitted_version: NO_GO
amendment_status: pending_independent_conformance
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 109ba3f4
audited_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
audit_commit: 9bbfd37a218222ae06c1f669b95dba37c4732765
amendment_branch: research/pao-r36-amendment
inspection_date: 2026-08-08
research_only: true
inspection_method: architect_supplied_complete_git_grep_plus_exact_ref_file_readback
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, archive, signer, publication-of-record venue, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - translation-parity mechanism design
  - recovery objective, retention period, expiry rule, or disaster-mode design
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 orientation and repository evidence ledger

## 1. Inspection boundary and P35 discipline

Documentation claims in this amendment are bound to `main@109ba3f4`. The architect established that
`policy-engine/src` at `109ba3f4` is byte-identical to the original source pin
`1a7a2d05ebba22fae80e9934329e4b880806588e`. Source-owner conclusions therefore carry forward; every
document reference is evaluated at the new docs pin.

The token census below is supplied by the architect's complete tree walk, not re-derived from the
connected search index:

- command class: `git grep` over the pinned ref;
- path denominator: `policy-engine/src`;
- match semantics: case-sensitive fixed strings;
- binary files: excluded; and
- file-type denominator: stated in every row.

P35's index rider is symmetric. An index cannot establish a zero and cannot establish a positive
count. It may omit a member in either case. This amendment records the complete-walk figures as the
controlling census and does not average them with connector results.

Counting vocabulary:

- **token-containing files**: distinct files with at least one exact occurrence;
- **matching lines**: physical source lines with at least one exact occurrence; and
- **occurrences**: non-overlapping exact substring occurrences.

These units and denominators are not interchangeable.

## 2. Audit count conflict and adjudication

### 2.1 `supersede`

The independent audit reported 47 files / 203 matching lines / 246 occurrences and called the
commission's 48-file value wrong. That correction is declined.

The failure mechanism is exact:

1. the true case-insensitive candidate set under `policy-engine/src` has 50 files;
2. the connector returned 49 candidates, omitting one tree member;
3. the audit correctly identified two returned files with zero lowercase occurrences:
   - `policy-engine/src/polisyos/foundry/methods/lifecycle/deprecation.py`, containing
     `SupersededBy...`; and
   - `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/validation.py`,
     containing `DATASET_SUPERSEDED`;
4. subtracting those two from the incomplete 49-candidate index set produced 47; and
5. the complete case-sensitive tree walk establishes 48 lowercase files.

The subtraction was sound; its indexed denominator was incomplete. This is the P35 index rider
biting a positive count.

### 2.2 Other audit undercounts

The audit's file count for lowercase `superseded` was correct at 34, but its line/occurrence counts
were short. Its `retraction` and `cache_invalidat` occurrence counts were each short by one. Its
`subscriber` count reproduces exactly.

The audit was right about the original denominator defect for `retraction`: six is the Python-only
count, while seven is the all-source count. The amendment records both denominators.

### 2.3 Zero claims

The original research correctly refused to promote zero connector results into universal absence.
The complete walk now settles all three zeroes. They are no longer `not_established`:

- `correction_notice`: 0 files / 0 lines / 0 occurrences;
- `notify_subscribers`: 0 / 0 / 0; and
- `correction_feed`: 0 / 0 / 0.

This strengthens, rather than weakens, the capability conclusion.

## 3. Complete token census

Common path denominator and method are fixed by §1.

| Exact token | File-type denominator | Files | Matching lines | Occurrences | Disposition |
| --- | --- | ---: | ---: | ---: | --- |
| `supersede` | all source; all 48 members are Python | **48** | **215** | **260** | Commission file count confirmed; audit correction declined. |
| `superseded` | all source | **34** | **154** | **183** | File count confirmed; audit line/occurrence counts corrected. |
| `retraction` | all source | **7** | **40** | **45** | All-source denominator. |
| `retraction` | Python only | **6** | **39** | **44** | Original commission's six named Python paths; denominator now explicit. |
| `cache_invalidat` | all source | **3** | **5** | **6** | Generic cache concerns only. |
| `subscriber` | all source | **3** | **18** | **21** | Generic subscriber text only. |
| `correction_notice` | all source | **0** | **0** | **0** | Settled complete-walk absence. |
| `notify_subscribers` | all source | **0** | **0** | **0** | Settled complete-walk absence. |
| `correction_feed` | all source | **0** | **0** | **0** | Settled complete-walk absence. |

### 3.1 Seven all-source `retraction` members

1. `policy-engine/src/polisyos/runtime/quality/policy_design_case.py`;
2. `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py`;
3. `policy-engine/src/polisyos/runtime/quality/calibration_ledger.py`;
4. `policy-engine/src/polisyos/runtime/quality/tenant_cas_approval_governance.py`;
5. `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`;
6. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`; and
7. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/README.md`.

The first six form the Python-only denominator. None establishes a public correction notice,
notification chain, or correction feed.

### 3.2 Three `cache_invalidat` members

1. `policy-engine/src/polisyos/foundry/methods/compiler/hot_reload.py`;
2. `policy-engine/src/polisyos/fabric/_adapters/observability.py`; and
3. `policy-engine/src/polisyos/fabric/connectors/cache/_store_core.py`.

These are reusable generic mechanisms, not a correction-scoped `C` registry, source generation,
member receipt, authority fence, or effective gate.

### 3.3 Three `subscriber` members

1. `policy-engine/src/polisyos/scholar/search/security.py`;
2. `policy-engine/src/polisyos/runtime/http/services/review_collaboration.py`; and
3. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py`.

They do not establish correction subscription scope, frozen cohorts/obligations, delivery intents,
receipts, retry/escalation, or a failure-visible aggregate.

## 4. Structural orientation at `109ba3f4`

| Proposition | Re-derived/retained evidence | Amended disposition |
| --- | --- | --- |
| INT-R7/R8 ratification record has 439 source lines | Exact read at docs pin returned lines 435-439 and no line 440. | **Agrees: 439.** Ratified findings are cited by ID, not surrounding prose. |
| `rule_evolution.py` has 839 source lines and 30 top-level declarations | Exact endpoint read at `109ba3f4` returned lines 836-839 and no line 840. Original complete declaration read found 28 column-zero functions plus 2 column-zero classes. Source SHA remains `e93ecbb...`. | **Agrees: 839; 28 + 2 = 30.** Nested protocol methods remain excluded. |
| `public_export.py` has 2,103 source lines | Exact read returned lines 2101-2103 and no later content; source SHA remains `12f9bb...`. | **Agrees: 2,103.** |
| `projection_semantics.py` has 3,763 source lines | Exact read returned lines 3761-3763 and no later content; source SHA remains `6874a2...`. | **Agrees: 3,763.** |
| Four projection audiences remain canonical | PUBLIC, REVIEWER, EXPERT, and MACHINE are owned by `projection_semantics.py`. | **Agrees.** No fifth correction audience is introduced. |
| `rule_evolution.py` is the owner to extend | Registry/replay/persistence/public annotation, producer/reader ownership, semantic-change blocking, and silent-upgrade prohibition remain co-located. | **Agrees.** Public-correction specialization remains absent. |
| Public export producer-to-HTTP relation is `bridge_missing` | Producer `build_public_export_bundle` exists. HTTP control-response shaping consumes `public_export`/`public_export_ref`, and the control-plane store invokes the shaper. Complete invocation census has no production builder call. | **Agrees.** Both endpoints exist; orchestration does not connect them. No signing path is established. |
| GY-N12 is the currentness owner | The plan at docs pin names append-only epoch/current-head/`as_of`/reissue chronology and forbids a parallel owner. | **Agrees; `contract_only`/undelivered.** |
| Atlas D4 fixes project language posture | D4 remains the project posture. | **Agrees.** Council Regulation No 1 is now cited only for governed institutional language enumeration; parity remains INT-R6. |
| INT-R7 controls key/proof semantics | Final decomposition, snapshot selection, obtainability, succession, and pre-issuance gate are in terminal Section 18 at `int-r7/public-verification-profile.md:620-760`. | **Agrees.** Earlier rows are historical detail read through §18. |
| P37 controls gate-predicate provenance | `policy-design-case-failure-patterns.md` at docs pin classifies load-bearing predicates and requires the falsify-the-declaration probe. | **Consumed.** The detailed PAO contract contains the complete table and admission freeze. |

## 5. Capability reality conclusion

The source asymmetry is settled:

- internal supersession/evolution is broad and has a canonical owner;
- a general public-export producer and HTTP consumer boundary exist but remain `bridge_missing`;
- no correction-specific notice, notification operation, or correction feed exists in source;
- no frozen correction surface/cache/subscriber/archive/language registry exists;
- GY-N12 is undelivered; and
- INT-R6 parity is unresearched.

Therefore:

- correction notice/feed/notification/cache/archive/parity/end-to-end chains are
  `absent/unallocated`;
- they are not `producer_missing`, because a correction consumer chain is not yet established;
- they are not `verification_missing`, because the end-to-end chain is not wired; and
- the amended research remains `accepted_narrow_scope`, `pending_independent_conformance`, and
  non-capability-bearing.

## 6. Amendment-specific orientation conclusion

R10 is closed in the research text by recording the architect-supplied complete census with both
path and file-type denominators. The amendment does not claim to have independently re-run that
census in this environment. Its evidence is the supplied complete-walk result, adjudicated against
the known connector omission mechanism and recorded without averaging.
