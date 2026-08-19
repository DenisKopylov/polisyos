---
title: "OPS-R14 Bounded Remediation Independent Delta Verification"
verification_id: OPS-R14-REMEDIATION-DELTA-VERIFICATION
status: completed_with_blocking_finding
verdict: NO_GO
prior_no_go_lifted: false
av_b01: CLOSED
av_b02: NOT_CLOSED
av_n01: CLOSED
blocking_findings: 1
non_blocking_delivery_findings: 1
verified_remediation_branch: research/ops-r14-remediation
verified_remediation_head: 62de2c5fe2123c6814596aaf08f3391e650305de
prior_verification_branch: research/ops-r14-amendment-verification
prior_verification_head: 0fe8fe6a0e53f23a90b92e06bad2d48543753693
prior_verification_blob: c403d273482fedea1bbae775e87c7810ee5420cf
amendment_head: 83539ebf0a211728cf3cb8cef4cbffce8429a8bb
independent_audit_head: 34c65a04ef178b9a59f70b9fb2012edee17a67cd
repository_documentation_pin: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
output_branch: research/ops-r14-remediation-verification
research_standing: accepted_narrow_scope
capability_standing: NO_GO
gate_standing: NO_GO
authoritative_for:
  - independent_delta_verdict_for_ops_r14_bounded_remediation
  - closure_adjudication_for_av_b01_av_b02_av_n01
  - remediation_delta_boundary_and_identity
may_not_use_for:
  - remediation_or_improvement_of_the_subject
  - re_adjudication_of_unrelated_accepted_audit_findings
  - production_implementation_authorization
  - production_capability_claim
  - permission_to_publish_sign_or_open_a_gate
  - final_wire_schema_package_database_serialization_or_api_contract
  - canonical_owner_vendor_custodian_archive_service_or_escrow_appointment
  - authority_or_delegation_grant
  - legal_sufficiency_or_jurisdictional_conclusion
research_only: true
---

# OPS-R14 bounded-remediation independent delta verification

## 0. Decision

**The prior `NO_GO` does not lift. Resulting package verdict: `NO_GO`.**

The remediation closes the census-provenance finding and the incomplete source-currentness refusal.
It does not close the succession/P37 blocker. The negative F-14B world is sound, but the new F-14A
positive route can still accept a purported authoritative record that is derived from, reachable by,
or shares a load-bearing substrate with the party whose succession it attests. The detector asserts
that the record is non-producing; it does not verify that property.

| Prior finding | Delta disposition | Reason |
| --- | --- | --- |
| `AV-B01` | **`CLOSED`** | Both denominators, the reproduction contract, `PP-01 = institutionally_supplied`, and the non-positive treatment of the three supplied zeroes are complete throughout the package. The unavailable recursive tree walk is an environmental limitation, not a package defect. |
| `AV-B02` | **`NOT_CLOSED`** | F-14B goes red with markers intact, but F-14A's positive path lacks a detector for whether its claimed non-producing record is actually independent of the attesting producer. R9 does not contain that provenance mechanism. |
| `AV-N01` | **`CLOSED`** | The historical review date and every surviving external-source currentness proposition are qualified; present currency remains `not_established` under PP-35. |

A separate non-blocking delivery-discipline gap remains: the remediation's supplied readback section
rendered an empty list, and no retained receipt proves that its author performed the required
post-write range readback. This verifier independently resolved the present branch identity by reading
all seven remediation files from the exact branch head; that does not retroactively establish the
missing author-side readback.

## 1. Delta boundary

### 1.1 Exact objects

| Object | Exact identity |
| --- | --- |
| Remediation | `research/ops-r14-remediation@62de2c5fe2123c6814596aaf08f3391e650305de` |
| Prior independent verification | `research/ops-r14-amendment-verification@0fe8fe6a0e53f23a90b92e06bad2d48543753693` |
| Prior verification file | blob `c403d273482fedea1bbae775e87c7810ee5420cf`, 415 lines |
| Amendment | `research/ops-r14-amendment@83539ebf0a211728cf3cb8cef4cbffce8429a8bb` |
| Independent audit | `research/ops-r14-independent-audit@34c65a04ef178b9a59f70b9fb2012edee17a67cd` |
| Registered P37 | `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` |

The remediation branch is identical to the reported head. Relative to the amendment head it is
**7 commits ahead and 0 behind**, with the amendment head as the exact merge base.

### 1.2 Exact changed file set, line counts, and blobs

The delta contains exactly seven Markdown files. Final line counts total **1,989**.

| Path | Status | Final lines | Blob at remediation head |
| --- | --- | ---: | --- |
| `policy-engine/docs/research/policy-operations/ops-r14-custody-resilience-and-expiring-authority.md` | modified | **514** | `99a38878c7564de04cc2ecf06f9a59c9faa5b1e9` |
| `policy-engine/docs/research/policy-operations/ops-r14/amendment-ledger.md` | modified | **127** | `9f47422cceb8e0e1a017d90ebff6ceff25e1460c` |
| `policy-engine/docs/research/policy-operations/ops-r14/disaster-fixtures-and-drill-evidence.md` | modified | **492** | `e7167c80c57fe237ff9b2963fa0ecc78ce701f30` |
| `policy-engine/docs/research/policy-operations/ops-r14/external-primary-source-and-transfer-ledger.md` | modified | **168** | `dcd51fdbab8833b4bbeba390755a654c3553829f` |
| `policy-engine/docs/research/policy-operations/ops-r14/long-term-replay-and-preservation.md` | modified | **316** | `2f463ded49df5a502068842e25df0ab9e4be2dd4` |
| `policy-engine/docs/research/policy-operations/ops-r14/orientation-ledger.md` | modified | **187** | `c3f2b06daa7d35cc9fdd0934ef08852126a4517b` |
| `policy-engine/docs/research/policy-operations/ops-r14/remediation-ledger.md` | added | **185** | `8f222265059cc890bf4219a3dc2e5378f679ae85` |
| **Total** | | **1,989** | |

The three unchanged working artifacts retain their amendment blobs:

| Unchanged artifact | Blob |
| --- | --- |
| `ops-r14/custody-class-objectives-and-recovery-closure.md` | `aa873ac91c2c48d19910ca0543497b6a54137dab` |
| `ops-r14/repository-integration-handoff.md` | `0adbb8a4709beea65b37d292329e2ae36dce9300` |
| `ops-r14/watched-dependency-and-legal-hold-semantics.md` | `8e902f852486abfd95a7150ca8bba5a66989204d` |

No source, test, workflow, binary, staging, transport, `AGENTS.md`, or
`policy-design-case-failure-patterns.md` path changed.

### 1.3 Semantic-delta traceability

| Changed artifact | Semantic delta | Trace |
| --- | --- | --- |
| Orientation ledger | Dual census, commands, supplied provenance, zero demotion | `AV-B01` only |
| Amendment ledger | Corrected dispositions and links to bounded remediation | `AV-B01`, `AV-B02`, `AV-N01` only |
| Disaster fixtures | F-14A/F-14B split and red succession probe | `AV-B02` only |
| External-source ledger | Historical/currentness qualifications | `AV-N01` only |
| Long-term replay | Succession split and positive/negative evidence paths | `AV-B02` only |
| Primary report | Package-level P37, census, succession, and currentness alignment | all three findings only |
| Remediation ledger | Scope, dispositions, reproduction information, and retest request | delivery record for the three findings |

No unrelated semantic improvement was found. Within `AV-B02`, however, the remediation introduces a
new positive-evidence mechanism and calls it an application of R9. That claim is false; the mechanism
is still traceable to the attempted B02 repair, but it is larger than a consistency-only correction
and remains under-specified.

## 2. `AV-B01` — complete supplied-census sweep

### 2.1 Reproduction contract and classification

The package now carries:

- pin `109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`;
- path denominator `policy-engine/src`;
- case-sensitive fixed-string matching;
- binary exclusion;
- the three commissioned recursive `grep` command templates;
- the architect's report of two clean-archive runs with identical results;
- both all-source and Python-only files/lines/occurrences for every token; and
- `PP-01 = institutionally_supplied`, not `recomputed`.

The dual-denominator table is complete:

| Token | All-source f/l/o | Python-only f/l/o |
| --- | ---: | ---: |
| `legal_hold` | `2 / 7 / 8` | `2 / 7 / 8` |
| `renewal` | `4 / 4 / 4` | `1 / 1 / 1` |
| `expires_at` | `50 / 281 / 364` | `49 / 280 / 363` |
| `ttl_seconds` | `30 / 116 / 148` | `30 / 116 / 148` |
| `expiry` | `28 / 103 / 122` | `27 / 102 / 121` |
| `grace_period` | `0 / 0 / 0` | `0 / 0 / 0` |
| `not_after` | `0 / 0 / 0` | `0 / 0 / 0` |
| `revocation_time` | `0 / 0 / 0` | `0 / 0 / 0` |

The all-source results expose the previously hidden non-Python member for both `expires_at` and
`expiry`. No current package argument uses the former Python-only tuple as though it were an
all-source denominator.

### 2.2 Package-wide positive-language enumeration

The sweep covered the nine amended artifacts plus the new remediation ledger.

| Artifact | Count-bearing statement or possible positive route | Adjudication |
| --- | --- | --- |
| Primary report | Census table, consequences, `PP-01`, renewal semantic conclusion | Every tuple is supplied; `PP-01` is non-positive; the three zeroes are `not_established`. The semantic capability conclusion is expressly based on owner/consumer/capability inspection rather than a lexical zero. |
| Orientation ledger | Census contract, reconciliation, semantic consequence, final numbered conclusions | “True zero,” “settled fact,” “established absence,” and “established by complete walk” are removed. All supplied counts are non-positive for this package. |
| Amendment ledger | `OPS-R14-I-002`, P35/census-provenance section | Records both denominators and the supplied/non-positive consequence. It no longer says R7 was closed by package recomputation. |
| Remediation ledger | AV-B01 reproduction table and disposition | Calls the census institutionally supplied and the zeroes not established. |
| Integration handoff | One Python `renewal` occurrence and narrow legal-hold implementation anchors | These low-cardinality propositions were independently reproduced by the prior verifier and are supported by named source paths; they do not depend solely on the supplied high-cardinality census. |
| Watched-dependency/hold artifact | The Python `renewal` occurrence is a worker lease | Same independently reproduced low-cardinality fact; it opens no authority gate. |
| Custody objectives | No source-census or lexical-zero proposition | No route. |
| Disaster fixtures | No source-census or lexical-zero proposition | No route. |
| External-source ledger | No source-census or lexical-zero proposition | No route. |
| Long-term replay | No source-census or lexical-zero proposition | No route. |

The statement that the audit's `legal_hold` tuple was wrong is not supported only by the architect's
supply: the prior independent conformance verification separately reproduced `2 / 7 / 8`. It is not a
surviving supplied-count positive.

### 2.3 Environmental limitation

This verifier still cannot execute the complete recursive tree walk. That is the same environmental
access limitation recorded across the wave. It is **not a package defect** after remediation because
the package no longer labels the census `recomputed` or uses the three supplied zeroes as established
facts.

**Disposition: `CLOSED`.**

## 3. `AV-B02` — F-14 delta and P37 attack

### 3.1 F-14B falsify-the-declaration execution

The semantic probe was evaluated with every declaration and marker retained:

| Element | Probe value |
| --- | --- |
| Successor identities | A and B unchanged |
| Scope markers | X, Y, and overlap unchanged |
| Admission marker | `admitted=true` unchanged |
| Instrument references | unchanged |
| Falsified property | exact bytes or the claimed authoritative record contradicts or fails authority, scope, timing, notice, conditions, or effective time |

Under the written F-14B detector, the exact bytes/receipt/record comparison fails, the predicate
remains `institutionally_supplied`, and the only permitted verdict is
`succession_scope_not_established`. `scoped_succession_partial` and every current-custodian positive
are expressly forbidden.

**F-14B goes red.** The negative half of the split tests the property rather than the marker.

### 3.2 F-14A positive-route attack

F-14A permits `scoped_succession_partial` because it calls the succession predicate
`independently_reconciled`. The load-bearing requirement is that the authoritative record be
**non-producing**.

The following adversarial case is admitted by the written detector:

1. Successor A supplies instrument `IA`, its scope declaration, and its admission material.
2. The named “authoritative record” is an export derived from A's submission, is writable through A's
   control account, or shares A's storage substrate and root signing key.
3. The record and `IA` contain identical authority, scope, timing, notice, condition, and effective-
   time fields.
4. The admission receipt resolves and all content digests match.
5. A marker or metadata field describes the record as non-producing.

The F-14A detector resolves exact bytes and receipts and compares their contents. It does not
reconstruct administration, derivation, storage, key, failure, or observation provenance for the
purported authoritative record. It therefore has no test that distinguishes the adversarial case from
an actually non-producing source. Every specified comparison can pass and the positive verdict can be
returned.

This is the P37 failure one level down: the gate relies on a declaration that its reconciling source is
non-producing. The package already knows how to test this class in F-15/PP-06, but F-14A neither invokes
that predicate nor incorporates its common-mode provenance detector.

### 3.3 R9 consistency claim

R9 says that a locally performed unilateral option exercise can pass only where the admitted
instrument grants it and the required scope, time/timing, competence, notice, and conditions are
proved. That is an admitted-instrument sufficiency test.

R9 does **not** require:

- a non-producing authoritative record;
- canonical admission receipts as an independent observation;
- administrative/storage/key-root separation from the attesting party; or
- derivation/provenance reconciliation of the validating record.

F-14A/PP-36 therefore adds a new evidence mechanism. It is not merely the previously present R9 test
applied consistently. The remediation's internal-inconsistency explanation is not established.

**Disposition: `NOT_CLOSED`.** The positive path remains vulnerable to a declaration-driven
independence premise, so the prior blocking finding remains operative.

## 4. `AV-N01` — complete source-currentness sweep

### 4.1 External-source ledger

The complete external ledger now has `source_currentness: not_established`. The
`source_review_date: 2026-08-06` value is expressly historical metadata and not evidence of present
currency.

Every previously identified currentness assertion is qualified:

1. 36 C.F.R. Part 1226 is described as text represented in the historical review record, with present
   currency not re-established.
2. The NARA/eCFR precedence statement is limited to the historical review record.
3. The U.S. Courts Rule 37(e) target is a recorded landing page whose exact current target was not
   reverified.
4. FAR 4.805 / FAC 2026-01 effective 2026-03-13 is an identity recorded in the review, with present
   currency not reverified.
5. The UK Call for Views and cited Act/guidance are historical review statements; the event and current
   source status are not independently re-established.

The complete row walk also qualifies the remaining potential sixth routes: the Title 44 and FOIA
locators, FEMA material, NIST publications, UK statutes/guidance, ISO/OAIS, PREMIS, and RFC publication
statuses are all recorded-source statements, not present-currentness findings. URLs containing a
`current` path component remain historical locators and are expressly insufficient under PP-35.

The synthesis and all four conflict/adjudication sections repeat the historical-review boundary.

### 4.2 Primary report and other artifacts

The primary report now says that stable identifiers and the transfer analysis are retained while
current official status, successor identity, live URL resolution, and continued source currency are
`not_established` pending PP-35 reconciliation. It imports no source-currentness finding.

The amendment ledger completes the R8 refusal on the same terms. Replay/F-06 already separates
historical source capture from current official status. Other uses of “currentness” concern GY-N12 or
authority-time semantics, not external-source currency.

No unqualified sixth external-source currentness assertion survives.

**Disposition: `CLOSED`.**

## 5. Required invariants

### 5.1 Standing fields

All working artifacts retain the exact reference shape:

- `research_standing: accepted_narrow_scope`
- `capability_standing: NO_GO`
- `gate_standing: NO_GO`

The remediation does not infer operational capability or gate permission from research acceptance.

### 5.2 R11 seam

The exact seam remains:

`RP-10 + RC-01 + RC-07 + F-04 + F-09 + DE-07`

There are **9 exact seam summaries** across **8 artifacts**:

1. primary report §4.4;
2. orientation ledger seam row;
3. custody objectives RC-07;
4. long-term replay RP-10;
5. disaster evidence DE-07;
6. integration handoff matrix PAO-R36 row;
7. integration handoff §4.3;
8. amendment ledger `OPS-R14-VIII-001`; and
9. remediation ledger §1.

Every occurrence is unchanged in substance and order. No `RP-10`-alone closure statement appears.

### 5.3 Accepted findings and protected paths

No unrelated accepted audit finding is reopened. Changes to the amendment ledger are confined to the
three later verification findings and their direct cross-references. The attempted extension of R9 is
adjudicated above as part of the still-open `AV-B02`; it does not alter R9's original text in the
unchanged watched-dependency artifact.

`AGENTS.md`, the failure-patterns register, all source paths, all workflows, and all binary paths are
unchanged.

## 6. Delivery readback evidence

The supplied remediation delivery report contains a heading saying that branch readback identities
are supported by first and final ranges, followed by an empty list. The committed remediation ledger
contains blob identities but no retained range-readback receipt. Accordingly, whether the remediation
author actually performed the required post-write readback is **not established**.

This is a delivery-discipline finding, not a semantic package change:

### DV-N01 — non-blocking — author-side range readback not evidenced

- The empty rendered list cannot prove performance.
- No staging-versus-branch mismatch is currently present: the remote branch resolves exactly to
  `62de2c5fe2123c6814596aaf08f3391e650305de`.
- This verifier fetched all seven remediation files from that branch and reproduced their blob
  identities listed in §1.2.

The independent readback establishes the current delivered branch state. It does not retroactively
supply the missing author-side delivery receipt.

## 7. Final classification

| Item | Result |
| --- | --- |
| `AV-B01` | **`CLOSED`** |
| `AV-B02` | **`NOT_CLOSED`** |
| `AV-N01` | **`CLOSED`** |
| Delivery discipline | **One non-blocking evidence gap: `DV-N01`** |
| Prior `NO_GO` lifted? | **No** |
| Resulting package verdict | **`NO_GO`** |

The inability to execute the architect's complete tree walk in this environment remains an
**environmental limitation rather than a package defect**. It does not drive the `NO_GO`. The verdict
is driven by F-14A's unverified non-producing-source premise.

All commissioned delta areas were reached. Nothing was left unclassified because of budget. This
verification makes no repair.
