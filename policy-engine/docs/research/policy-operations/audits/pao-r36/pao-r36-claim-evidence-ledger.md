---
title: PAO-R36 - Claim Evidence Ledger
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_load_bearing_claim_evidence_mapping
  - pao_r36_claim_support_dispositions
  - pao_r36_consolidation_traceability
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

# PAO-R36 claim evidence ledger

## 1. Method

This ledger maps every load-bearing PAO-R36 proposition to the evidence that is supposed to support
it and records whether the evidence actually does so. “Supported with revision” means that the
underlying proposition survives but the submitted expression is internally inconsistent,
under-specified, or not yet falsifiable. “Not supported as submitted” means that at least one
compliant reading of the submitted package defeats the proposition.

Repository claims are evaluated at the pin. Research-contract claims are evaluated at the audited
head. Ratified propositions are cited by finding ID rather than by adjacent prose.

## 2. Claim ledger

| Claim ID | Load-bearing PAO-R36 claim | Audited evidence | Audit verdict | Controlling finding |
| --- | --- | --- | --- | --- |
| CL-01 | Correction is an append-only successor relation; the predecessor is not rewritten or erased. | Primary report `pao-r36-public-correction-and-durable-notice.md:58-83, 135-153`; detailed contract `pao-r36/ordered-fanout-and-completeness-contract.md:41-58, 160-177`; F03 at `pao-r36/falsifier-suite.md:91-108`; ratified `PV-K02` and `S0-K08`. | **Supported.** The research consumes the law and adds an identity/graph detector. | `PAO-R36-VII-001`, commendation. |
| CL-02 | `t_authority` and `t_effective` are distinct public boundaries. | Primary report `:205-216`; detailed contract `:61-82`; effective step `:357-379`. | **Concept supported; submitted order not supported.** The primary report transitions authority before arming the fence and publishing the notice, contradicting the detailed contract. | `PAO-R36-III-001`, blocking; `PAO-R36-III-006`, commendation. |
| CL-03 | Between the boundaries, a controlled observer can see only successor-current-linked, predecessor-historical-linked, or fail-closed unavailable. | Primary predicate `:284-310`; detailed state table and predicate `pao-r36/ordered-fanout-and-completeness-contract.md:61-82, 430-459`. | **Supported with material revision.** The three high-level classes are useful, but the predicate does not bind correction identity, notice phase, authenticated cutoff, or projection/language relation, so a semantically fourth observation remains reachable. | `PAO-R36-III-004`, material; `PAO-R36-III-007`, commendation. |
| CL-04 | The authority fence prevents predecessor-current from the instant of `t_authority`. | Detailed Step 9 requires the fence before transition at `ordered-fanout-and-completeness-contract.md:300-326`; primary Step 9 places it after transition at `pao-r36-public-correction-and-durable-notice.md:235-244`. | **Not supported as submitted.** One authoritative summary permits a crash window with no armed fence. | `PAO-R36-III-001`, blocking. |
| CL-05 | The correction notice is visible no later than authority transition. | Detailed Step 3 at `ordered-fanout-and-completeness-contract.md:178-199`; primary Step 10 publishes after transition at `pao-r36-public-correction-and-durable-notice.md:239-247`. | **Not supported as submitted.** A compliant primary-report execution can expose successor-current before the notice is published. | `PAO-R36-III-001`, blocking. |
| CL-06 | `t_stage <= t_authority <= t_effective` and no surface may invent an earlier effective time. | Primary report `:205-216`; detailed contract `:61-82`; F13 `pao-r36/falsifier-suite.md:257-275`. | **Supported only as prose.** No event-order predicate, append-order verifier, or backdated/equal-time falsifier is defined. | `PAO-R36-III-005`, material. |
| CL-07 | Every “all X” claim is over a frozen enumerated denominator. | Primary sets and formal rule `pao-r36-public-correction-and-durable-notice.md:258-283`; detailed sets and completeness definition `ordered-fanout-and-completeness-contract.md:83-113`; F16 `falsifier-suite.md:307-320`. | **Largely supported.** The discipline is unusually strong, but the `R` set contains the effective declaration that Step 12 requires to be complete before that declaration is appended. | `PAO-R36-III-002`, blocking; `PAO-R36-IV-003`, commendation. |
| CL-08 | `Complete(R)` can be a precondition of `t_effective`. | Primary `R` definition includes the effective declaration at `pao-r36-public-correction-and-durable-notice.md:258-267`; detailed Step 12 requires `Complete(R)` before appending it at `ordered-fanout-and-completeness-contract.md:357-379`. | **Not supported.** The precondition is circular/self-dependent. | `PAO-R36-III-002`, blocking. |
| CL-09 | A synchronous member cannot be moved to asynchronous status after the correction begins. | Step 0 identifies whether a `P` decision is required at `ordered-fanout-and-completeness-contract.md:113-125`; Step 8 later lets the classifier decide whether actual receipt is pre-effect at `:278-301`; primary Step 13 uses “may require” at `pao-r36-public-correction-and-durable-notice.md:247-252`. | **Not supported.** The membership snapshot is frozen, but the applicability of the receipt gate is not explicitly frozen. | `PAO-R36-III-003`, blocking. |
| CL-10 | Frozen `S` and `C` snapshots establish completeness for controlled surfaces and caches. | Primary set definitions `:258-283`; detailed Step 0 and Step 11 `ordered-fanout-and-completeness-contract.md:113-125, 337-356`; F02/F04. | **Supported with material revision.** No registry-generation lock prevents a new controlled route/cache variant from appearing after snapshot and before effect. | `PAO-R36-IV-001`, material. |
| CL-11 | Uncontrolled copies are explicit exclusions and no claim implies the internet is cleared. | Primary `:268-270`; detailed `:102-105, 459-467`; F14 `falsifier-suite.md:276-290`; transfer ledger does not appoint external publishers. | **Supported.** No contradictory universal-completion statement was found. | `PAO-R36-IV-002`, commendation. |
| CL-12 | A risk-increasing correction is decidable at protocol level without declaring legal sufficiency. | Primary hard case `pao-r36-public-correction-and-durable-notice.md:313-337`; comparative fixture `pao-r36/comparative-models-and-hard-cases.md:103-147`; F10 `falsifier-suite.md:211-226`; Charter Article 41 transfer is expressly bounded. | **Supported.** Unknown adverse-impact classification blocks; the institutional decision remains external. | `PAO-R36-V-001`, commendation. |
| CL-13 | A legally significant superseded version remains retrievable and bound to decisions made under it, without automatic retroactivity. | Primary `:338-356`; comparative fixture `comparative-models-and-hard-cases.md:148-184`; F13. | **Supported.** The disposition reaches an executable version/`as_of` outcome and preserves the separate institutional legal-effect proposition. | `PAO-R36-V-002`, commendation. |
| CL-14 | A correction crossing a revoked-key event keeps issuance authenticity, compromise certainty, key authorization, and current authority separate. | Primary `:357-381`; comparative fixture `:185-230`; F09 `falsifier-suite.md:190-210`; controlling INT-R7 amendment §18. | **Substantively supported.** The research consumes INT-R7 rather than redesigning key lifecycle, but its citations should point to the terminal controlling section as well as earlier profile rows. | `PAO-R36-V-003`, commendation; `PAO-R36-VIII-003`, minor. |
| CL-15 | F01-F16 are executable specifications with exact outcomes. | Outcome vocabulary `falsifier-suite.md:25-44`; individual fixtures `:60-320`. | **Partly supported.** Each fixture has an oracle, but F03, F05, F08, F11, and F13 use conditional, phase-dependent, set-wide, or under-specified expected outcomes. | `PAO-R36-VI-001`, material. |
| CL-16 | F13 detects temporal inversion rather than merely testing a field. | F13 `falsifier-suite.md:257-275`. | **Supported.** It queries both sides of the authority cutoff and compares exact version/currentness. It does not, however, test event append order or backdating. | `PAO-R36-VI-002`, commendation; `PAO-R36-III-005`, material. |
| CL-17 | F16 detects a self-attested completion receipt that survives member deletion. | F16 `falsifier-suite.md:307-320`. | **Supported.** Removing one live member result while preserving aggregate markers must fail the independent join. | `PAO-R36-VI-003`, commendation. |
| CL-18 | The suite covers multiple corrections to the same record. | F08 tests two current heads at `falsifier-suite.md:173-189`. | **Not supported.** Two stale-base corrections can serialize to one head while the later correction bypasses the earlier successor; F08 can remain green. | `PAO-R36-VI-004`, material. |
| CL-19 | Completion receipts are independently recomputable and cannot be replayed across corrections. | General completeness rule and F16 bind member evidence but do not explicitly attack a valid receipt from another correction/snapshot with the same member/count. | **Not supported.** Cross-correction receipt replay is uncovered. | `PAO-R36-VI-005`, material. |
| CL-20 | A correction notice preserves PV-K04-protected meaning and cannot amplify authority/currency/permission. | Primary notice semantics `pao-r36-public-correction-and-durable-notice.md:382-426`; detailed Section 9 `ordered-fanout-and-completeness-contract.md:468-510`; F06. | **Supported.** The retained-item list and adversarial omission test make the ratified rule detectable. | `PAO-R36-VII-002`, commendation. |
| CL-21 | PAO-R36 does not create a second currentness/evolution owner. | Integration map `pao-r36/repository-integration-and-dependencies.md:31-77`; GY-N12 plan; `rule_evolution.py`; ratified `INT-K05` analogy. | **Supported.** It repeatedly routes chronology to `rule_evolution.py`/GY-N12 and refuses a PAO-specific owner. | `PAO-R36-VII-003`, commendation. |
| CL-22 | OPS-R14 and PAO-R36 close the no-un-correct seam without crossing ownership. | PAO handoff `repository-integration-and-dependencies.md:132-183`; F11; OPS-R14 `long-term-replay-and-preservation.md` RP-10 at `3a694212a`. | **Supported at interface level.** OPS-R14 preserves versions/head/completion evidence and blocks publication when PAO completion evidence is absent; PAO does not set recovery objectives. | `PAO-R36-VIII-001`, commendation. |
| CL-23 | INT-R6 is declared as a dependency, not solved. | Integration handoff `repository-integration-and-dependencies.md:112-131`; detailed Step 7 and F01 expressly require the future interface. | **Supported.** Protected-query parity is the required proposition; no translation workflow, algorithm, or format is designed. | `PAO-R36-VIII-002`, commendation. |
| CL-24 | Existing `public_export.py` is correctly labelled `bridge_missing`. | Producer in `runtime/quality/public_export.py`; HTTP control-response consumer in `runtime/http/services/control/response_shapes.py`; store calls response shaper; invocation census proves no production builder call. | **Supported.** Both endpoints exist and their orchestration connection does not. | `PAO-R36-IX-001`, commendation. |
| CL-25 | Correction notice/feed/subscriber/cache/archive capabilities are not falsely labelled `producer_missing` or `verification_missing`. | Integration map `repository-integration-and-dependencies.md:31-103`; capability vocabulary `policy-design-case-failure-patterns.md:14-35`. | **Supported.** The work uses `absent/unallocated` until prerequisite endpoints/chain exist. | `PAO-R36-IX-002`, commendation. |
| CL-26 | Statistical-agency revision practice transfers as an analogue, not authority. | External ledger EU-06 and UK-01..04 `external-primary-source-and-transfer-ledger.md:38-55`; ESS Guidelines DOI `10.2785/42763`; ONS central policy and revision triangles. | **Supported.** Transfer is limited to policy, classification, vintages, explanation, and analysis; signer authority, individual effect, and legal significance are expressly excluded. | `PAO-R36-II-001`, commendation. |
| CL-27 | Accessibility sources establish that recourse itself is a correction-completeness duty. | External rows EU-04 and UK-08 `external-primary-source-and-transfer-ledger.md:36, 58`. | **Overstated.** The sources require accessibility/feedback statements; they support accessibility of any otherwise-required recourse, not creation of the substantive recourse obligation. | `PAO-R36-II-002`, minor. |
| CL-28 | Regulation No 1 establishes language-invariant semantic identity. | External row EU-03 `external-primary-source-and-transfer-ledger.md:35`. | **Overstated.** It establishes the institutional language regime; the semantic-identity requirement comes from PAO-R36/INT-R6, not the Regulation. | `PAO-R36-II-004`, minor. |
| CL-29 | The cited COPE DOI unambiguously identifies the audited edition. | SCH-01 `external-primary-source-and-transfer-ledger.md:62`; DOI `10.24318/cope.2019.1.4`. | **Needs edition pin.** The DOI now resolves to Version 3, August 2025, while many citations still name the 2019 edition. The transfer survives, but edition/date must be explicit. | `PAO-R36-II-003`, minor. |
| CL-30 | `accepted_narrow_scope` is honest because the repository cannot currently issue a correction. | Primary standing `pao-r36-public-correction-and-durable-notice.md:31-53`; integration labels; current-state comparator. | **Substantively right but not consolidation-ready.** The capability refusal is honest; the central contract needs blocking revisions before the result can stand unchanged. | `PAO-R36-X-002`, commendation with `NO_GO` audit disposition pending revision. |

## 3. Evidence conclusion

The evidentiary base supports the research's central policy choice: append-only correction, two
separate public boundaries, enumerated denominators, explicit uncontrolled-copy exclusions, and
separate treatment of adverse corrections, old-version significance, and revoked keys. It does not
support the exact submitted execution order, the self-referential `R` gate, or the mutability of the
pre-effect notification rule. Those are not implementation details; they determine whether the
claimed safety invariant is true.
