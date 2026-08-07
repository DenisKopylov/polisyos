---
title: PAO-R36 - Hostile Independent Audit
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_independent_audit_verdict
  - pao_r36_complete_finding_register
  - pao_r36_audit_count_reconciliation
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 hostile independent audit

## 1. Executive verdict

**Audit disposition: `NO_GO` as submitted.**

This disposition does not change PAO-R36's standing by fiat. It means the audited
`accepted_narrow_scope` package cannot enter consolidation unchanged. The capability refusal and the
narrow scope are honest; the load-bearing semantic contract is not yet internally coherent.

Three blocking defects control the result:

1. the primary report transitions current authority before the authority fence and public notice,
   while the detailed contract requires both before the transition;
2. `Complete(R)` is a precondition for appending the effective declaration even though the effective
   declaration is itself a member of `R`; and
3. the decision that actual affected-party receipt is synchronous can remain mutable after the
   correction transaction begins.

The result also has seven material findings, five minor findings, and twenty-four commendations. The
strong parts should survive revision: the two-boundary idea, explicit frozen denominators, bounded
external-copy claims, the adverse/old-version/revoked-key dispositions, F09, F13, F16, owner-first
integration, and the OPS-R14/INT-R6/INT-R7 seams.

## 2. Audited delivery verification

Comparison of the pin to the audited head reproduces the commissioned delivery exactly:

- 9 commits ahead, 0 behind;
- merge base exactly `1a7a2d05ebba22fae80e9934329e4b880806588e`;
- 7 added Markdown files;
- 2,297 additions;
- 0 modified files and 0 deleted files.

The file arithmetic is:

`684 + 538 + 374 + 241 + 216 + 174 + 70 = 2,297`.

No workflow, source-code, package, binary, upload fragment, staging directory, or self-executing
artifact appears in the audited diff.

## 3. Count reconciliation

### 3.1 Finding counts

| Severity | Count |
| --- | ---: |
| blocking | **3** |
| material | **7** |
| minor | **5** |
| commendation | **24** |
| **Total** | **39** |

The prose and table agree: **39 findings = 3 blocking + 7 material + 5 minor + 24 commendations**.
There are no unregistered narrative findings in this audit package.

### 3.2 Orientation counts

| Exact token / structure | Re-derived result | Reconciliation |
| --- | --- | --- |
| `supersede` | 47 files / 203 matching lines / 246 occurrences | Commission 48 is wrong; audited research left it unresolved. |
| `superseded` | 34 / 152 / 180 | Commission 34 is correct. |
| `retraction`, all source files | 7 / 40 / 44 | Six is correct only for the Python-only denominator. |
| `retraction`, Python files | 6 / 39 / 43 | Named six Python paths reproduce. |
| `cache_invalidat` | 3 / 5 / 5 | Reproduces file count. |
| `subscriber` | 3 / 18 / 21 | Reproduces file count. |
| `correction_notice` | `not_established` complete-walk zero | Connector returned zero; no recursive exact-pin tree walk was available. |
| `notify_subscribers` | `not_established` complete-walk zero | Same. |
| `correction_feed` | `not_established` complete-walk zero | Same. |
| `rule_evolution.py` | 839 lines; 28 top-level functions + 2 top-level classes | Reproduces 30 declarations. |
| `public_export.py` | 2,103 lines | Reproduces. |
| `projection_semantics.py` | 3,763 lines | Reproduces. |
| INT-R7/R8 ratification | 439 lines | Reproduces. |

The complete derivation and denominators are in
[`pao-r36-orientation-error-ledger.md`](pao-r36-orientation-error-ledger.md).

## 4. Complete finding register

### Pass I — orientation

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-I-001` | material | Exact lowercase `supersede` count is 47, not the unresolved inherited 48. | Audited claim/refusal at `policy-engine/docs/research/policy-operations/pao-r36/orientation-ledger.md:49-57`; exact-case reconciliation over all 49 connector candidates gives 47/203/246. Required revision R10. |
| `PAO-R36-I-002` | minor | `retraction` denominator correction omits matching-line and occurrence counts. | `pao-r36/orientation-ledger.md:58-78`; completed figures are all-file 7/40/44 and Python 6/39/43. |
| `PAO-R36-I-003` | commendation | Structural line and declaration counts reproduce. | `pao-r36/orientation-ledger.md:103-124`; pinned files end at 439, 839, 2,103, and 3,763 lines, with 28+2 top-level declarations. |
| `PAO-R36-I-004` | commendation | Generic cache/subscriber token hits are not laundered into correction capability. | `pao-r36/orientation-ledger.md:80-101`; exact source paths are generic cache/security/collaboration/academic components. |
| `PAO-R36-I-005` | commendation | Zero indexed results are not overstated as complete-walk absence. | `pao-r36/orientation-ledger.md:30-64`; the research explicitly marks the connector boundary. |

### Pass II — external sources

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-II-001` | commendation | Statistical revision practice is transferred seriously and within its limits. | `pao-r36/external-primary-source-and-transfer-ledger.md:38,51-55`; Eurostat `KS-RA-13-016`, DOI `10.2785/42763`, and ONS policies support policy/classification/vintages/revision analysis, not signer authority or individual legal effect. |
| `PAO-R36-II-002` | minor | Accessibility sources are used as if they create substantive recourse. | External rows EU-04 and UK-08 at `external-primary-source-and-transfer-ledger.md:36,58`. Narrow to accessibility of otherwise-required recourse/feedback. |
| `PAO-R36-II-003` | minor | COPE DOI has no edition/date pin. | SCH-01 at `external-primary-source-and-transfer-ledger.md:62`; DOI `10.24318/cope.2019.1.4` currently resolves to Version 3, August 2025. |
| `PAO-R36-II-004` | minor | Regulation No 1 does not establish language-invariant semantic identity. | EU-03 at `external-primary-source-and-transfer-ledger.md:35`; CELEX `31958R0001` supports governed language enumeration/publication, while semantic identity belongs to INT-R6/PAO. |
| `PAO-R36-II-005` | commendation | Legal/publication regimes are not cited as direct PolicyOS duties. | Transfer synthesis at `external-primary-source-and-transfer-ledger.md:64-70` excludes competence, deadlines, legal effect, hearing/notice sufficiency, venue, retention, and remedy. |

### Pass III — two-boundary contract

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-III-001` | blocking | Primary and detailed contracts give opposite order for authority transition, fence, and notice publication. | Primary `pao-r36-public-correction-and-durable-notice.md:218-253`; detailed notice/fence/transition at `pao-r36/ordered-fanout-and-completeness-contract.md:178-199,300-344`. Two compliant crash sequences produce forbidden observations. R1. |
| `PAO-R36-III-002` | blocking | `Complete(R)` is circular because `R` includes the effective declaration. | Primary `R` at `pao-r36-public-correction-and-durable-notice.md:258-267`; detailed precondition/effect at `ordered-fanout-and-completeness-contract.md:357-379`. R2. |
| `PAO-R36-III-003` | blocking | Synchronous receipt applicability can change after transaction admission. | `ordered-fanout-and-completeness-contract.md:113-125,278-301`; primary `:247-253`. Membership is frozen, but the decisive receipt predicate is not. R3. |
| `PAO-R36-III-004` | material | The three-label observer predicate omits correction identity, notice phase, `as_of`, projection, and language parity. | `pao-r36-public-correction-and-durable-notice.md:284-310`; a wrong/staged notice can satisfy the label. R4. |
| `PAO-R36-III-005` | material | `t_stage <= t_authority <= t_effective` is asserted without event-order/anti-backdating verification. | `pao-r36-public-correction-and-durable-notice.md:205-216`; detailed `ordered-fanout-and-completeness-contract.md:61-82`; F13 tests version selection, not append order. R5. |
| `PAO-R36-III-006` | commendation | The two-boundary construction is an original and useful systems result. | Same boundary definitions; it separates current authority from bounded dissemination completion. |
| `PAO-R36-III-007` | commendation | Safe mixed-state convergence is correctly preferred to impossible physical atomicity. | Observer model at `pao-r36-public-correction-and-durable-notice.md:284-310`; retain after tuple/order repair. |

### Pass IV — enumerated completeness

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-IV-001` | material | `S/C` can gain a new controlled member after snapshot and before effect. | Set/freeze rules at `pao-r36-public-correction-and-durable-notice.md:258-283` and `ordered-fanout-and-completeness-contract.md:83-125`; no registry-generation continuity rule. R6. |
| `PAO-R36-IV-002` | commendation | Uncontrolled copies are explicit exclusions; no internet-cleared claim is made. | `ordered-fanout-and-completeness-contract.md:102-105,459-467`; F14 `falsifier-suite.md:276-290`. |
| `PAO-R36-IV-003` | commendation | Completeness is structurally bound to snapshots, members, counts, cutoffs, exclusions, and independent recomputation. | `pao-r36-public-correction-and-durable-notice.md:258-283`; detailed `ordered-fanout-and-completeness-contract.md:83-113`; F16. |

### Pass V — hard cases

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-V-001` | commendation | The risk-increasing case reaches a decidable block/admit outcome without declaring legal sufficiency. | `pao-r36/comparative-models-and-hard-cases.md:103-147`; F10 `falsifier-suite.md:211-226`. |
| `PAO-R36-V-002` | commendation | The legally significant predecessor remains version-bound and intelligible for past decisions. | `comparative-models-and-hard-cases.md:148-184`; no automatic voidness/retroactivity. |
| `PAO-R36-V-003` | commendation | The revoked-key case consumes INT-R7 and separates four propositions. | `comparative-models-and-hard-cases.md:185-230`; F09; controlling INT-R7 §18 at `int-r7/public-verification-profile.md:620-760`. |

### Pass VI — falsifier suite

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-VI-001` | material | F03, F05, F08, F11, F13—and F06's unnamed member—are not one unambiguous exact outcome each. | `pao-r36/falsifier-suite.md:91-165,173-275`; conditional/disjunctive/phase-dependent/set-wide outcomes. R7. |
| `PAO-R36-VI-002` | commendation | F13 is a sharp `as_of` inversion attack. | `falsifier-suite.md:257-275`; it tests both historical and current selection around the cutoff. |
| `PAO-R36-VI-003` | commendation | F16 is a genuine remove-property/keep-markers probe. | `falsifier-suite.md:307-320`; independent join must fail when one member result disappears. |
| `PAO-R36-VI-004` | material | F08 misses serialized stale-base corrections with one head at every instant. | F08 `falsifier-suite.md:173-189`; C1 `v1->v2`, then stale C2 `v1->v3` can lose C1 without a fork. R8. |
| `PAO-R36-VI-005` | material | Suite misses replay of all valid receipts from another correction/snapshot. | General member binding and F16 do not explicitly bind every receipt to correction identity, predicate, selected version/notice, and cutoff. R9. |
| `PAO-R36-VI-006` | commendation | F09 is a real bidirectional laundering attack, not kernel restatement. | `falsifier-suite.md:190-210`; later revocation cannot erase issuance, and old signature validity cannot mint current authority. |

### Pass VII — kernel conformance

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-VII-001` | commendation | `PV-K02`/`S0-K08` are made detectable. | F02/F03/F07/F09/F11 test currentness, identity immutability, archive linkage, key semantics, and restore. |
| `PAO-R36-VII-002` | commendation | `PV-K04` binds correction-notice compression. | Notice requirements at `pao-r36-public-correction-and-durable-notice.md:382-426`; F06. |
| `PAO-R36-VII-003` | commendation | No second evolution/currentness owner is created. | Integration map `pao-r36/repository-integration-and-dependencies.md:31-103`; `rule_evolution.py`, GY-N12, and four existing audiences are reused. |

### Pass VIII — seams

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-VIII-001` | commendation | OPS-R14 seam closes from both sides without ownership crossing. | PAO requirements `repository-integration-and-dependencies.md:132-183`; OPS-R14 RP-10 at `ops-r14/long-term-replay-and-preservation.md:184-201`, plus hold/expiry semantics in its separately audited branch. |
| `PAO-R36-VIII-002` | commendation | INT-R6 is an interface dependency, not a smuggled mechanism. | `repository-integration-and-dependencies.md:112-131`; F01 delegates equivalence evidence to INT-R6. |
| `PAO-R36-VIII-003` | minor | Final INT-R7 claims cite historical rows without always citing terminal controlling §18. | PAO citations to `int-r7/public-verification-profile.md:250-405`; controlling section is `:620-760`. R11. |

### Pass IX — capability honesty

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-IX-001` | commendation | `bridge_missing` for existing public export is correctly evidenced on both endpoints. | Producer `runtime/quality/public_export.py:102-120`; HTTP response consumer in `runtime/http/services/control/response_shapes.py`; store calls response shaper; complete invocation census has no production builder call. |
| `PAO-R36-IX-002` | commendation | Correction notice/feed/subscriber/cache/archive/end-to-end verification use `absent/unallocated` rather than prerequisite-invalid labels. | `pao-r36/repository-integration-and-dependencies.md:31-103`; vocabulary prerequisites at `policy-design-case-failure-patterns.md:14-35`. |

### Pass X — prohibitions and standing

| ID | Severity | Finding | Evidence and disposition |
| --- | --- | --- | --- |
| `PAO-R36-X-001` | commendation | All seven artifacts preserve the required prohibitions. | Frontmatter in `pao-r36-public-correction-and-durable-notice.md:1-29`; `pao-r36/ordered-fanout-and-completeness-contract.md:1-20`; `pao-r36/falsifier-suite.md:1-20`; `pao-r36/comparative-models-and-hard-cases.md:1-20`; `pao-r36/repository-integration-and-dependencies.md:1-20`; `pao-r36/orientation-ledger.md:1-22`; `pao-r36/external-primary-source-and-transfer-ledger.md:1-22`. No erasure, implementation authorization, translation mechanism, recovery objective, expiry rule, legal-sufficiency claim, or publication-gate opening is proposed. |
| `PAO-R36-X-002` | commendation | `accepted_narrow_scope` is substantively honest about capability absence. | Standing at `pao-r36-public-correction-and-durable-notice.md:31-53`; current-state comparator and integration labels refuse a live correction claim. Audit remains `NO_GO` until R1-R10 close. |

## 5. Capability-label audit

The capability vocabulary is used correctly:

- `public_export.py` producer plus HTTP control-response consumer, without a production builder bridge,
  satisfies the prerequisites of `bridge_missing`;
- no correction notice/feed/subscriber consumer is first assumed in order to manufacture
  `producer_missing`;
- no unwired correction chain is mislabeled `verification_missing`; and
- GY-N12 remains an undelivered named currentness contract rather than a claimed capability.

This is an important strength because prerequisite-invalid maturity labels were blocking defects in
the previous wave.

## 6. Prohibition audit

Across the seven artifacts, no text:

- proposes erasure or in-place rewrite of a published predecessor;
- creates a parallel correction/evolution/currentness owner;
- defines translation-parity mechanics;
- sets recovery objectives, retention periods, expiry periods, renewal semantics, or disaster modes;
- declares any notification legally sufficient;
- claims the repository can currently issue a public correction;
- appoints a vendor, archive, service, signer, or publication-of-record venue; or
- authorizes implementation or opening the first-public-record gate.

The research is appropriately prose-only and branch-contained.

## 7. Required disposition

The architect should preserve the research's scope and strengths but require the executable revision
register R1-R10 before accepting its standing unchanged. The fastest safe path is not a rewrite:
reconcile the order, remove the circular gate, freeze notification applicability, strengthen the
observer tuple/event order, bind registry generation and receipts, split ambiguous fixtures, add two
missing attacks, and correct Pass I arithmetic.

The exact revision register is
[`pao-r36-recommended-revision.md`](pao-r36-recommended-revision.md).
