---
title: INT-R1 — Claim–Evidence Ledger
status: delivered
kind: independent-audit
research_task: INT-R1
result_type: accepted_narrow_scope
audit_verdict: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-independent-audit
audited_branch: research/int-r1-obligation-coverage
audited_commit: 82e136a8d528cb24e661973ac1a8ea4fb6f1c80f
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - machine-checkable audit disposition of load-bearing INT-R1 claims
  - evidence base for INT-R1 consolidation decisions
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - merger or release approval
research_only: true
---

# INT-R1 — Claim–Evidence Ledger

## 1. Verdict vocabulary

- **verified** — evidence supports the claim as written.
- **verified_narrower** — core proposition survives, but wording/scope must narrow.
- **design_only** — coherent research specification; not implemented or empirically passed.
- **unsupported_as_stated** — evidence does not support the claim at its stated strength.
- **refuted** — evidence contradicts the claim.
- **not_applicable** — not a factual or formal claim capable of this audit disposition.

No load-bearing claim was assigned `refuted`. Material revisions are concentrated in the
relative-theorem interpretation, actual independence, enum/Rule-12 wording, and executability of
the decisive-obligation mutation fixture.

## 2. Repository and scope claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-001 | The audited work is six commits, six new Markdown files, 4,242 insertions, no code/test/existing-document changes. | diff summary and main frontmatter | Compare `d152565d...82e136a8`; six added `.md` files only. | **verified** | INT-R1-H-005 |
| CL-002 | The research used `d152565d` rather than the old `4813b49f6` baseline. | main `:75-115`; census `:31-70` | Commit IDs and 121-commit comparison verified. | **verified** | INT-R1-A-001 |
| CL-003 | Current main is 121 commits ahead and zero behind the historical baseline. | census `:31-43` | Git compare metadata. | **verified** | INT-R1-I-002 |
| CL-004 | `PromotionObligationClass` has 15 members, not 14. | main `:177-205`; census `:43-56` | Enumerated source at `gy_waist.py:218-235`; `VALUE` present. | **verified** | INT-R1-I-001 |
| CL-005 | The supplied 14-member orientation was wrong rather than evidence of recent enum growth. | census `:43-56` | Same 15-member definition at both pinned commits. | **verified** | INT-R1-I-001 |
| CL-006 | The report creates no canonical owner or package placement. | main §§7-8; all six files | Diff inspection and language review; owner map says “prefer”/“unresolved,” not appointment. | **verified** | INT-R1-H-005 |
| CL-007 | `accepted_narrow_scope` matches the established result. | all frontmatter; main §4 | Unconditional open-world completeness is denied; only conditional relative coverage is retained. | **verified_narrower** | Requires D-001/D-002 wording before consolidation. |

## 3. Current δ-ledger and denominator claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-008 | The ledger explicitly conditions `P(false promotion)≤δ` on obligation completeness and validator soundness. | main `:206-266`; census §2.2 | `confidence_ledger.py:37-50`. | **verified** | INT-R1-A-001 |
| CL-009 | Maintained assumptions are typed/carried into multiple durable records. | main `:206-266` | `confidence_ledger.py:500-1010`, `:2463-2488`. | **verified** | INT-R1-A-001 |
| CL-010 | Pools must partition the enum with no duplicate/omitted classes. | main `:206-266` | `confidence_ledger.py:337-369`. | **verified** | INT-R1-A-001 |
| CL-011 | Pool weights must sum exactly to one. | main `:206-266` | `confidence_ledger.py:337-369`. | **verified** | INT-R1-A-001 |
| CL-012 | The risk split is content-bound as `obligation_split_hash`. | main `:206-266` | Root/receipt construction and output at `confidence_ledger.py:500-1010`, `:2463-2488`. | **verified** | INT-R1-A-001 |
| CL-013 | N9 validates an ordered tuple equal to `tuple(PromotionObligationClass)` and denominator mismatch affects refusal/promotion. | main §2.4; census §2.3 | `promotion_sequence.py:1320-1900`. | **verified** | INT-R1-A-001 |
| CL-014 | The current N9 compiler emits one obligation record per coarse enum class. | benchmark audit | `_compile_obligations` at `promotion_sequence.py:1900-2140`; `PromotionObligationRecord` at `gy_waist.py:280-390` has a class but no obligation-instance ID. | **verified** | INT-R1-H-002 |
| CL-015 | Exact denominator/weight totality proves internal allocation relative to the enum, not the world's obligation universe. | main `:250-310` | Logical scope of the checks plus owned-source code inspection. | **verified** | INT-R1-D-004 |
| CL-016 | Live registry profile kinds are two ineligible, one unavailable theorem, one deterministic, one e-process; two schedules use Basel square. | main §2.3; census §2.2 | `confidence_ledger.toml:1-89`. | **verified** | INT-R1-I-002 |
| CL-017 | The pinned proving-ground state supplies no positive governed-conversion/useful-design population for calibrating miss risk. | main §2.3; census §9 | G5 plan and `layer3_g5_readiness_manifest.json`: zero conversion, zero useful-design credit, unchanged blocker, 13 typed blockers in current W12.D statement. | **verified_narrower** | Scope to the pinned corpus snapshot; INT-R1-I-003. |
| CL-018 | A numeric probability for unknown remainder cannot presently be empirically calibrated from repository history. | main §2.3, §4.7 | Profile kinds are not miss observations; pinned corpus has no positive sample. | **verified** | No probability claim is allowed. |

## 4. P29 and Rule-12 claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-019 | P29 permits stopping at generic traversal over the actual owned source of truth with typed exemptions and review. | main §2.5; census §4 | `policy-design-case-failure-patterns.md:70-75`. | **verified** | INT-R1-D-004 |
| CL-020 | That stopping rule transfers to owned schemas, fixed basis entries, and registered routes. | main §2.5 | Formal property matches P29's actual-source premise. | **verified** | INT-R1-D-004 |
| CL-021 | It does not by itself prove selection of all external-world obligation sources. | main §2.5 | External world is not an owned complete object graph; no repository source claims otherwise. | **verified** | INT-R1-D-004 |
| CL-022 | Rule 12 explicitly exempts governed vocabularies/statuses while banning hand-maintained capability-gating enumerations. | main §2.4; census §3 | Organizing rules `:200-222`. | **verified** | INT-R1-G-001 |
| CL-023 | The enum is “currently a capability-gating enumeration” and therefore a Rule-12 defect. | main §2.4; census §§2.3-3 | Exact tuple participates in a gate, but the same object is also a versioned governed denominator vocabulary. Rule 12 defect follows only if it is treated as exhaustive universe or blocks free-growth obligation instances. | **unsupported_as_stated; valid only use-conditionally** | INT-R1-G-001 |
| CL-024 | Preserving the enum as a coarse governed vocabulary while refusing it as proof of world completeness is defensible. | main §2.4 | Consistent with Rule 12's explicit exemption and with exact-version denominator checks. | **verified** | Preserve this narrower table-based analysis. |

## 5. Impossibility-result claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-025 | If two admissible worlds produce the same finite trace but one has an unseen decisive obligation, no trace-only procedure can soundly and positively certify both. | main `:549-586`; formal note | Stepwise indistinguishability proof. | **verified_narrower** | INT-R1-C-001 |
| CL-026 | The result does not say a narrow domain can never be closed. | main `:570-579` | Explicit caveat in report; logically correct. | **verified** | Preserve. |
| CL-027 | A competent exhaustive register/valid closure premise can rule out the extension world for a scope. | main `:570-579` | Correct logical escape from extension-closure premise. | **verified as possibility, not repository capability** | INT-R1-C-001 |
| CL-028 | More search never becomes proof of absence by quantity alone. | main `:579-586` | Valid while unseen-extension premise remains admissible. | **verified_narrower** | State the premise each time. |
| CL-029 | Randomization cannot distinguish observationally identical worlds without an external distribution/closure assumption. | main `:579-586` | Same conditional output law from identical observation; external prior would add assumptions. | **verified** | INT-R1-C-002 |
| CL-030 | The report establishes that all actual PolicyOS obligation domains satisfy the open-world premise. | implied broad reading only | No per-domain closure/openness census was produced. | **unsupported_as_stated** | The report mostly avoids this claim; consolidation must not add it. INT-R1-C-001. |

## 6. Relative-coverage claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-031 | Under nine premises every obligation derivable from `B` under language/compiler `v` is in `O_T` and checked. | main `:592-647`; formal note | Deductive audit. R4 substantially contains the inclusion property; R6 contains validator correctness. | **verified as conditional entailment** | INT-R1-D-001 |
| CL-032 | The theorem proves `C_v(B)=U(W)`. | expressly denied at main `:632-647` | Report denies; no evidence supplies equality. | **refuted proposition, correctly rejected by deliverable** | Commendation. |
| CL-033 | R4 discharges compiler semantic completeness. | main premise 4 | R4 assumes compiler soundness/completeness relative to basis semantics. | **unsupported_as_stated** | INT-R1-D-001 |
| CL-034 | R6 discharges validator soundness. | main premise 6 | R6 assumes the same semantic property as target-spec A4. | **unsupported_as_stated** | INT-R1-D-001 |
| CL-035 | R7 independent checker is logically required once R4/R6 are assumed. | main premise 7 | Independence is evidence for those assumptions, not a deductive antecedent needed after truth is stipulated. | **unsupported_as theorem structure** | INT-R1-D-002 |
| CL-036 | Independent review/mutation/governance are valid admissibility evidence for relying on R4/R6. | main §§4.5-4.7 | Transfer from audit/testing/assurance literature and P29; fallible but checkable. | **verified as protocol** | INT-R1-D-002 |
| CL-037 | Independence is constructed by the deliverable. | main §4.6; artifact sketch | Dimensions/fields are specified; no independent producer/scorer is implemented or appointed. | **unsupported_as capability** | INT-R1-D-003 |
| CL-038 | The report's five-row stopping table correctly separates owned traversal, relative derivation, validator evidence, institutional judgment, and open remainder. | main §4.5 | Row-by-row formal audit. | **verified_narrower** | INT-R1-D-004 |
| CL-039 | A false premise silently degrades to a pass in the proposed protocol. | main §§4.3, 7.4, state machine | Proposed mappings refuse/unknown/scope-insufficient; no auto-pass. | **refuted concern at design level** | Cleared; implementation absent. |
| CL-040 | The pinned repository can currently issue `bounded_complete`. | capability claims/census | Independent checker, envelope, governance producer, and bridge are missing. | **refuted** | Must explicitly remain unavailable; INT-R1-D-003. |

## 7. Coverage assessments, one lattice, and authority claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-041 | The three labels are evidence assessments, not authority outcomes or a total order. | main §4.3 | Text and mapping explicitly say so. | **verified as design** | INT-R1-F-001 |
| CL-042 | `bounded_complete` means relative basis/language completeness and never all-world completeness. | main `:648-676` | Definition and public qualifier. | **verified as design** | INT-R1-F-001 |
| CL-043 | `bounded_complete` never auto-maps to `satisfied` or promotion. | main §7.4 | Mapping gives only `NO_COVERAGE_BLOCKER`; substantive statuses decide separately. | **verified_narrower** | Derived token must not become persisted status; INT-R1-F-002. |
| CL-044 | `known_incomplete`/`open_world_unresolved` block affected protected action while candidate work may continue under declared limitation. | main §§4.3, 7.4 | Consistent with S0-K06 band split. | **verified as design** | INT-R1-F-001 |
| CL-045 | Missing, stale, contradictory, revoked, expired, or suspended decisive evidence cannot become a pass. | main §§5, 7.4-7.6 | Explicit failure/unknown/suspension paths; consistent with S0-K12. | **verified as design** | INT-R1-F-001 |
| CL-046 | Coverage passage grants compliance, competence, or authority. | main deny-lists | Expressly denied; S0-K16 also denies authority by passage. | **refuted proposition, correctly rejected** | Commendation. |
| CL-047 | Atlas may decide coverage from projection. | main §§1,8; Atlas constitution | Expressly denied; Atlas is renderer/consumer. | **refuted proposition, correctly rejected** | S0-K05 preserved. |

## 8. Typed artifact and lifecycle claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-048 | `ObligationCoverageEnvelope` includes declared scope, searched sources, exclusions, unknown remainder, TTL/currentness, provenance, review, challenge, and deny-lists. | main §7.1; artifact sketch | Field-by-field inspection. | **verified as typed research sketch** | INT-R1-H-001 |
| CL-049 | A producer may self-fill the envelope and thereby establish `bounded_complete`. | main §5 counterexample; §7.1 prerequisites | Independent review, governance, mutation and unresolved-common-mode checks are mandatory. | **refuted concern at design level** | P29 self-attestation cleared. |
| CL-050 | `ValidatorGovernanceRecord` includes rule owner, change process, independent-check identities/hashes, common-mode risks, incidents, TTL, and supersession. | main §7.2; artifact sketch | Field-by-field inspection. | **verified as typed research sketch** | INT-R1-H-001 |
| CL-051 | Artifact sketches establish canonical wire/schema/package owners. | main §7 disclaimers | Explicitly denied. | **refuted proposition, correctly rejected** | Scope discipline passed. |
| CL-052 | Challenger process accepts later missed obligations/validator faults and triggers append-only perturbation, suspension, revalidation, reissue, and public notice. | main §§7.3, 7.5; artifact sketch | State/transition/event inspection. | **verified as design** | INT-R1-H-001 |
| CL-053 | Old records are silently edited/reopened after a miss. | main state machine | Original becomes historical/superseded/withdrawn; new envelope/event created. | **refuted proposition, correctly rejected** | CTM semantics preserved. |
| CL-054 | TTL alone establishes no unknown obligation exists. | main §§5, 7.6 | Expressly denied; event triggers override calendar TTL. | **verified** | Consistent with CTM. |
| CL-055 | Mandatory edge cases are present: happy path, missing decisive obligation, late discovery, unsound validator, conflict, unavailable owner, degraded mode, partial success, rollback, replay. | main §6.7; benchmark artifact | All ten specified. | **verified as fixture design** | INT-R1-H-001 |

## 9. Benchmark and P29-object-level claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-056 | Benchmark expectations are frozen independently and not generated by the compiler under test. | main §6.2; benchmark artifact | Explicit oracle and independence rules. | **verified as design** | INT-R1-E-001 |
| CL-057 | The deliverable constructs/ratifies the independent scorer. | main §6.2, §6.8 | Explicitly deferred to S0-GAP-02. | **refuted** | Honest deferral; INT-R1-E-001. |
| CL-058 | Any benchmark component self-scores from primary compiler output. | all six files | No such allowed path; same-code/self-oracle invalidates run. | **refuted concern** | Cleared. |
| CL-059 | “δ proof red” blocks both protected action and current public claim. | main §6.5 | Explicit booleans false and lifecycle reaction. | **verified as required result** | INT-R1-H-004 |
| CL-060 | Red merely reports a breach while authority remains green. | main §§6.1, 6.5, 6.8 | Explicitly called benchmark failure. | **refuted concern** | Cleared. |
| CL-061 | OM-01 can be implemented directly against the current N9 representation while preserving another same-class obligation. | main §§6.3-6.4 | Current N9 emits one record per class and has no obligation-instance identity/aggregation layer. | **unsupported_as_stated** | INT-R1-H-002 |
| CL-062 | OM-01 conceptually defeats pure class-counting. | main §§6.3-6.4 | Two source-derived instances share `normative`; deletion leaves class present in the proposed future instance model. | **verified conceptually, implementation bridge missing** | INT-R1-H-002 |
| CL-063 | The fixture defeats any possible “keyword check.” | main §6.3 | It defeats naive class/marker/generic-text checks; an arbitrary semantic keyword oracle is undefined. | **unsupported_as broadly worded** | INT-R1-H-003 |
| CL-064 | VM-01 requires independent detection of an always-true/unknown-to-satisfied validator and propagation to refusal/suspension. | main §6.4 | Concrete expected property chain specified. | **verified as benchmark design** | INT-R1-H-001 |
| CL-065 | Benchmark was implemented or passed. | main §6.8 and all files | Explicitly says not implemented/run and `semantic_test_missing`; no contradiction found. | **refuted proposition, correctly rejected** | INT-R1-E-002 |

## 10. External-transfer claims

| Claim ID | Load-bearing claim | Audited location | Verification method and evidence | Verdict | Finding |
| --- | --- | --- | --- | --- | --- |
| CL-066 | Normative-system completeness is relative to declared universes/cases/solutions. | external ledger §§2-3; main §3.1 | Book existence verified; detailed page-level attribution not independently available from cited catalog record. | **verified_narrower** | INT-R1-B-001 |
| CL-067 | Cook supports a relative-completeness framing but not adequacy of the semantic oracle/language. | external ledger; main §3.2 | SIAM primary abstract and theorem framing. | **verified** | INT-R1-B-002 |
| CL-068 | RDF/SHACL support explicit scoped closure, not truth of the closure premise. | main §3.3 | W3C Recommendations. | **verified** | INT-R1-B-002 |
| CL-069 | Circumscription formalizes a closure/default choice rather than discovering absence. | external ledger | Stanford primary text. | **verified** | INT-R1-B-002 |
| CL-070 | STPA/IEC/HSE support structured, stakes-sensitive diligence, not exhaustive obligation proof. | main §3.4 | MIT, IEC, HSE primary sources and explicit non-transfer. | **verified** | INT-R1-B-002 |
| CL-071 | SACM/GSN structure assurance claims/evidence but do not prove truth/completeness. | main §3.5 | OMG/SCSC primary standards. | **verified** | INT-R1-B-002 |
| CL-072 | Defeater practice supports challenge/reopening but cannot prove no unidentified defeater. | main §3.5 | SEI primary report; report states limit. | **verified** | INT-R1-B-002 |
| CL-073 | NASA confidence study supports rejecting an invented scalar confidence for unknown remainder. | main §3.5 | NASA/TM-2016-219195 conclusion. | **verified** | INT-R1-B-002 |
| CL-074 | Audit standards support sufficiency/appropriateness, independence, contradictions, documentation, and append-only additions. | main §3.6 | PCAOB AS 1105/1215 and GAO 2024. | **verified with non-applicability disclaimer** | INT-R1-B-002 |
| CL-075 | Mutation and MC/DC prove adequacy only relative to a declared fault/structural model. | main §3.7 | DeMillo et al.; NASA MC/DC; report states limit. | **verified** | INT-R1-B-002 |
| CL-076 | E-processes retain optional-stopping validity within a modeled process but do not discover obligations or prove semantic soundness. | main §3.8 | Ramdas et al. primary manuscript/DOI. | **verified** | INT-R1-B-002 |

## 11. Overall claim disposition

| Category | Result |
| --- | --- |
| Verified or verified with narrowing | Most load-bearing repository, formal, authority-boundary, and lifecycle claims survive within their stated scope. |
| Design-only, correctly labeled | Typed artifacts, state machine, challenger process, and benchmark protocol remain unimplemented research designs. |
| Unsupported at stated strength and requiring material revision | CL-023, CL-033, CL-034, CL-035, CL-037, CL-040, CL-061, and CL-063 identify the over-strong readings that consolidation must not ratify. |
| Refuted propositions that the deliverable itself rejects | These are honesty checks rather than defects: no world-completeness proof, no auto-promotion, no self-scoring, and no benchmark passage. |
| Blocking false load-bearing claim | None. Overall verdict remains `GO_WITH_REVISIONS`. |

The machine-checkable consolidation gate is: do not promote any `unsupported_as_stated` claim
into the ratified result. The negative open-world result, relative-only public rider, one-lattice
mapping, append-only challenge semantics, and explicit benchmark non-passage are safe to retain.