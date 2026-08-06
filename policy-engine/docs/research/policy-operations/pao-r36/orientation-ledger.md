---
title: PAO-R36 - Orientation and Repository Evidence Ledger
research_id: PAO-R36
status: delivered_research
result_standing: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
inspection_date: 2026-08-06
research_only: true
inspection_method: connected_exact_ref_interface_due_to_blocked_git_egress
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 orientation and repository evidence ledger

## 1. Inspection boundary and delivery discipline

Every repository proposition in this package is bound to commit
`1a7a2d05ebba22fae80e9934329e4b880806588e` on `main`. The delivery branch was created from that
exact commit.

Ordinary Git egress was unavailable and `gh` was not installed. The research therefore used the
commission-permitted connected GitHub exact-ref interface. No CI workflow, base64 upload fragment,
staging directory, or self-executing repository artifact was used.

The connector can read exact files and run exact-ref path-bounded searches, but it cannot execute the
requested local whole-tree counting script. P35 therefore requires a split verdict: exact file reads
and finite returned sets are reported, while search-result counts are not promoted into a complete
literal census. The limitation is part of the result rather than hidden by a false success claim.

Counting vocabulary is fixed as follows:

- `source-line count`: physical newline-delimited lines in one exact file;
- `matched-line count`: lines containing at least one exact, case-sensitive token;
- `literal-occurrence count`: non-overlapping exact substring occurrences;
- `token-containing-file count`: distinct files containing at least one exact token; and
- `connector candidate-file count`: distinct exact-ref search results, which is not represented as a
  P35-complete whole-tree walk.

These units are not interchangeable.

## 2. Pass I token census audit

Search boundary was `policy-engine/src` at the pin.

| Exact token | Brief claim: files | Exact-ref connector observation | Matched lines | Literal occurrences | Pass I disposition |
| --- | ---: | --- | --- | --- | --- |
| `supersede` | 48 | 49 distinct candidate files | not established | not established | **Disagreement.** The inherited 48 is not independently verified; connector search is not the required complete literal script. |
| `superseded` | 34 | 37 distinct candidate files | not established | not established | **Disagreement** under the same P35 limitation. |
| `retraction` | 6 | 7 files total: 6 Python files and 1 README | not established | not established | **Denominator error.** Six agrees only for an unstated Python-file denominator; the stated all-file source denominator has seven returned files. |
| `cache_invalidat` | 3 | 3 distinct files | not established | not established | **Connector agreement on file count**, not a complete occurrence census. |
| `subscriber` | 3 | 3 distinct files | not established | not established | **Connector agreement on file count**, not a complete occurrence census. |
| `correction_notice` | 0 | 0 indexed path-bounded results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement**, not an overstated script-proved universal absence. |
| `notify_subscribers` | 0 | 0 indexed path-bounded results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement** with the same boundary. |
| `correction_feed` | 0 | 0 indexed path-bounded results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement** with the same boundary. |

### 2.1 The seven `retraction` files

1. `policy-engine/src/polisyos/runtime/quality/policy_design_case.py`;
2. `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py`;
3. `policy-engine/src/polisyos/runtime/quality/calibration_ledger.py`;
4. `policy-engine/src/polisyos/runtime/quality/tenant_cas_approval_governance.py`;
5. `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`;
6. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`; and
7. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/README.md`.

The first six are the Python withdrawal paths named by the commission. The seventh proves why the
denominator must be stated. None establishes a public correction notice, subscriber fan-out, or
correction feed.

### 2.2 The three `cache_invalidat` files

1. `policy-engine/src/polisyos/foundry/methods/compiler/hot_reload.py`;
2. `policy-engine/src/polisyos/fabric/_adapters/observability.py`; and
3. `policy-engine/src/polisyos/fabric/connectors/cache/_store_core.py`.

They show generic cache invalidation concerns, not a correction-scoped cache inventory, invalidation
receipt, or effective-correction gate.

### 2.3 The three `subscriber` files

1. `policy-engine/src/polisyos/scholar/search/security.py`;
2. `policy-engine/src/polisyos/runtime/http/services/review_collaboration.py`; and
3. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py`.

They do not establish a correction subscriber registry, cohort, or failure-visible delivery chain.

## 3. Structural orientation audit

| Orientation proposition | Re-derived evidence at the pin | Disposition |
| --- | --- | --- |
| The INT-R7/R8 ratification record is 439 lines | An exact endpoint read returned lines 436-439 and no line 440 from `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md`. | **Agrees: 439 source lines.** |
| `rule_evolution.py` is the canonical evolution owner | It declares the shared registry, replay, public annotation, producer/reader owners, and public-policy blocker at `policy-engine/src/polisyos/core/contracts/rule_evolution.py:1-38`; its capability-reality record names producer, artifact, bridge, consumer, verification, and surface at `:177-189`. | **Agrees on owner.** Extend, do not duplicate. |
| `rule_evolution.py` has 30 top-level classes/functions | A complete four-range read of all 839/839 lines found 28 column-zero `def` declarations and 2 column-zero `class` declarations, with no column-zero `async def`. | **Agrees: 28 + 2 = 30.** The nested protocol method is excluded. |
| Silent semantic upgrade is prohibited | The public annotation sets `silent_upgrade_allowed` false and binds closed-case replay to original logic at `rule_evolution.py:302-330`. | **Agrees.** PAO-R36 makes the prohibition detectable; it does not re-ratify it. |
| `public_export.py` is 2,103 lines | An exact endpoint read returned lines 2101-2103 and no line 2104 from `policy-engine/src/polisyos/runtime/quality/public_export.py`. | **Agrees: 2,103 source lines.** |
| `projection_semantics.py` is 3,763 lines | An exact endpoint read returned lines 3761-3763 and no line 3764 from `policy-engine/src/polisyos/runtime/quality/projection_semantics.py`. | **Agrees: 3,763 source lines.** |
| `projection_semantics.py` owns four audiences | The enum declares PUBLIC, REVIEWER, EXPERT, and MACHINE at `projection_semantics.py:648-655`. | **Agrees.** No fifth correction audience is proposed. |
| `public_export.py` has a producer but no production HTTP caller | The prior complete invocation census found the definition, two tools, and two tests, with no HTTP caller at `policy-engine/docs/research/policy-operations/int-r8/orientation-ledger.md:145-166`. | **Agrees.** The existing relation is `bridge_missing`, not `producer_missing`. |
| `public_export.py` is signed | Exact in-file searches found no `signature` or `signing` token and no production signing bridge was established. | **Not established.** It must not be represented as a signed public correction capability. |
| `projection_semantics.py` owns omission, gap, contest, recourse, redaction, and audit-reference behavior | INT-R8 re-derived the helpers and audience contract at `int-r8/orientation-ledger.md:180-198`; the source owner contains the corresponding projection machinery. | **Agrees.** A notice must reuse it. |
| GY-N12 owns epoch/currentness/reissue chronology | GY-N12 declares append-only model-revision epochs, current heads, stale/revalidation behavior, and forbids a parallel correction chronology at `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2052-2138`. | **Agrees, contract-only/undelivered.** Consume by name. |
| Atlas D4 fixes language posture | D4 states `uk` primary, `en` baseline/fallback, and `ru` UI `legacy_continuity_frozen` - not used and not deleted - at `policy-engine/docs/brand/ATLAS_SOURCE_OF_TRUTH.md:262-275`. | **Agrees.** Equivalence mechanics remain INT-R6. |
| INT-R7 supplies key-lifecycle semantics | INT-R7 separates historical signature authenticity from current authorization, preserves predecessor proofs across rotation, and treats uncertain compromise overlap as indeterminate at `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:250-405`. | **Agrees, delivered profile.** Consume; do not redesign. |

## 4. Fixed findings, cited by ID

P36 forbids authority by adjacency. The controlling findings are cited by their IDs:

- `PV-K01`: current authority is separately reportable and cutoff-bounded;
- `PV-K02`: historical authenticity and current authority are distinct and non-erasing;
- `PV-K04`: a projection may reduce detail but may not amplify truth, certainty, authority,
  currency, or permission;
- `S0-K08`: correction appends; history is not rewritten;
- `P27` and `P28`: extend the canonical owner and do not leave a parallel default path;
- `P35`: every complete-set claim needs a complete enumerated denominator; and
- `P36`: cite the actual finding and reproduce its arithmetic.

Pinned anchors are
`policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:92-151`,
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:101`, and
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:71-80`.

## 5. Capability-state vocabulary audit

The repository defines a capability as a typed contract/artifact plus producer, persisted artifact or
event, orchestration bridge, consumer, verification, visible surface or explicit out-of-scope
statement, and a negative/end-to-end semantic test at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:16-35`.

The prerequisite-sensitive rules are:

- `producer_missing` requires a named consumer that expects an artifact/event but no deployed
  producer;
- `bridge_missing` requires both producer and consumer with no orchestration connection; and
- `verification_missing` requires an already wired chain that lacks end-to-end automated proof.

Therefore:

- the existing public-export producer with no HTTP production caller is `bridge_missing`;
- correction notice/feed/subscriber capabilities are **absent/unallocated**, not
  `producer_missing`, because no admitted correction consumer contract was found;
- correction-scoped cache and archive fan-out are **absent/unallocated** until their controlled set
  and consumer obligations are admitted; and
- the full correction chain is not `verification_missing` because there is no wired chain to verify.

## 6. Orientation conclusion

The qualitative asymmetry survives, but not every inherited number does. Internal supersession is
extensively represented while named outward-correction tokens have zero indexed connector results.
The 48/34 supersession file counts remain unverified and disagree with connector candidate sets. The
all-file `retraction` denominator is seven rather than six. The 439-line ratification record, the
30 top-level declarations in `rule_evolution.py`, the 2,103-line public export, and the 3,763-line
projection owner reproduce exactly.

The correct posture is to bind every set claim to its denominator, mark unavailable literal counts as
not established, and make no capability claim from token presence or absence alone.

## 7. `may_not_use_for`

This ledger may not be used for production implementation authorization; a final wire, schema,
package, database, serialization, media-type, or API contract; canonical owner, vendor, or service
appointment; an authority grant; a capability claim; legal sufficiency or a jurisdictional
conclusion; permission to publish or open a gate; or automatic amendment of any plan, backlog, or
system-design decision.
