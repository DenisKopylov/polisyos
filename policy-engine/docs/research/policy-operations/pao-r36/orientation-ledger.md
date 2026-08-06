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

The repository baseline for every repository proposition in this package is commit
`1a7a2d05ebba22fae80e9934329e4b880806588e` on `main`. The delivery branch was created from that
exact commit.

Ordinary Git egress was unavailable in the execution environment and `gh` was not installed. The
research therefore used the connected GitHub exact-ref interface permitted by the commission. No CI
workflow, base64 upload fragment, staging directory, or self-executing repository artifact was used.
This limitation matters for Pass I: the connector can fetch exact files and issue exact-ref path
searches, but it cannot run the requested local whole-tree counting script. Claims below distinguish
what was reproduced exactly from what remains not established. This follows the branch-readback rule
in `AGENTS.md:27` and the complete-denominator rule P35 at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:79`.

Counting vocabulary is fixed as follows:

- `source-line count`: physical newline-delimited lines in one exact file;
- `matched-line count`: lines containing at least one exact, case-sensitive token;
- `literal-occurrence count`: non-overlapping exact substring occurrences;
- `token-containing-file count`: distinct files containing at least one exact token;
- `connector candidate-file count`: distinct exact-ref search results returned by the connected
  interface; this is evidence of disagreement or agreement but is not represented as a P35-complete
  whole-tree walk.

A matched-line count, literal-occurrence count, and file count are different units. No row silently
converts one into another.

## 2. Pass I token census audit

Search boundary for the rows below was `policy-engine/src` at the pinned commit. The brief supplied
file counts. The connector supplied path-bounded exact-ref search result sets. Because no complete
local walk could be executed, the connector result is not promoted into a whole-tree literal census.

| Exact token | Brief claim: files | Exact-ref connector observation | Matched lines | Literal occurrences | Pass I disposition |
| --- | ---: | --- | --- | --- | --- |
| `supersede` | 48 | 49 distinct candidate files | not established | not established | **Disagreement.** The inherited 48 is not independently verified; the connector returned 49 files, but its search semantics are not a substitute for the required complete literal script. |
| `superseded` | 34 | 37 distinct candidate files | not established | not established | **Disagreement.** The inherited 34 is not independently verified; the connector returned 37 files, with the same P35 limitation. |
| `retraction` | 6 | 7 files total: 6 Python files and 1 README | not established | not established | **Denominator error.** Six agrees only if the unstated denominator is Python files. The stated all-file `policy-engine/src` denominator contains seven results. |
| `cache_invalidat` | 3 | 3 distinct files | not established | not established | **Connector agreement on file count**, not a complete occurrence census. |
| `subscriber` | 3 | 3 distinct files | not established | not established | **Connector agreement on file count**, not a complete occurrence census. |
| `correction_notice` | 0 | 0 search results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement.** A complete local walk remains unavailable, so this is not overstated as script-proved absence. |
| `notify_subscribers` | 0 | 0 search results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement** with the same limitation. |
| `correction_feed` | 0 | 0 search results | 0 indexed matched lines | 0 indexed occurrences | **Connector agreement** with the same limitation. |

### 2.1 The seven `retraction` files

The exact-ref result set is:

1. `policy-engine/src/polisyos/runtime/quality/policy_design_case.py`;
2. `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py`;
3. `policy-engine/src/polisyos/runtime/quality/calibration_ledger.py`;
4. `policy-engine/src/polisyos/runtime/quality/tenant_cas_approval_governance.py`;
5. `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`;
6. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`; and
7. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/README.md`.

The first six are the internal withdrawal paths named in the commission brief. The seventh proves
why the denominator must be stated. None of these search results establishes a public correction
notice, subscriber fan-out, or correction feed.

### 2.2 The three `cache_invalidat` files

The connector result set is:

1. `policy-engine/src/polisyos/foundry/methods/compiler/hot_reload.py`;
2. `policy-engine/src/polisyos/fabric/_adapters/observability.py`; and
3. `policy-engine/src/polisyos/fabric/connectors/cache/_store_core.py`.

These occurrences show that cache invalidation exists as a general technical concern. They do not
establish a correction-scoped cache inventory, invalidation receipt, or effective-correction gate.

### 2.3 The three `subscriber` files

The connector result set is:

1. `policy-engine/src/polisyos/scholar/search/security.py`;
2. `policy-engine/src/polisyos/runtime/http/services/review_collaboration.py`; and
3. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py`.

These occurrences do not establish a public-correction subscriber registry, notification cohort, or
failure-visible delivery chain.

## 3. Structural orientation audit

| Orientation proposition | Re-derived evidence at the pin | Disposition |
| --- | --- | --- |
| `rule_evolution.py` is the canonical evolution owner | The file declares the shared rule-evolution registry, replay, public annotation, producer/reader owners, and an explicit public-policy blocker at `policy-engine/src/polisyos/core/contracts/rule_evolution.py:1-38`; its capability-reality record names producer, artifact, bridge, consumer, verification, and surface at `:177-189`. | **Agrees on owner.** It must be extended, not duplicated. |
| `rule_evolution.py` has 30 top-level classes/functions | Complete exact-file declaration search found 18 top-level `def`, 2 top-level `class`, and 0 top-level `async def`: 20 total. | **Disagrees.** The exact top-level declaration count is 20, not 30. Constants and nested methods are not top-level classes/functions. |
| Silent semantic upgrade is already prohibited | The public annotation sets `silent_upgrade_allowed` false and binds closed-case replay to original logic at `rule_evolution.py:302-330`. | **Agrees.** PAO-R36 makes this publicly detectable; it does not re-ratify it. |
| `public_export.py` is 2,103 lines | The prior complete-file INT-R8 orientation re-derived 2,103 lines at `policy-engine/docs/research/policy-operations/int-r8/orientation-ledger.md:88-105`. | **Agrees.** |
| `projection_semantics.py` is 3,763 lines and owns four audiences | The prior complete-file ledger records 3,763 lines and PUBLIC, REVIEWER, EXPERT, MACHINE at `int-r8/orientation-ledger.md:104-113`; the enum is also visible at `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:648-655`. | **Agrees.** No fifth correction audience is proposed. |
| `public_export.py` has a producer but no production HTTP caller | The complete prior invocation census found five files: definition, two tools, and two tests; no HTTP path calls it at `int-r8/orientation-ledger.md:145-166`. | **Agrees.** The correct missing-state label is `bridge_missing`, not `producer_missing`. |
| `public_export.py` is signed | Exact in-file searches found no `signature` or `signing` token, and no production signing bridge was established. | **Not established.** The present bundle must not be represented as a signed public correction capability. |
| `projection_semantics.py` owns omission, gap, contest, recourse, redaction, and audit-reference behavior | INT-R8 re-derived the existing helpers and audience contract at `int-r8/orientation-ledger.md:180-198` and the source imports/use are visible throughout `projection_semantics.py`. | **Agrees.** A notice must reuse this owner. |
| GY-N12 owns epoch/currentness/reissue chronology | GY-N12 declares append-only model-revision epochs, current heads, stale/revalidation behavior, and forbids silent mutation or a parallel correction chronology at `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2052-2138`. | **Agrees, contract-only/undelivered.** PAO-R36 consumes the owner by name. |
| Atlas D4 fixes language posture | D4 is ratified: `uk` primary, `en` baseline/fallback, and `ru` UI catalog `legacy_continuity_frozen` - not used and not deleted - at `policy-engine/docs/brand/ATLAS_SOURCE_OF_TRUTH.md:262-275`. | **Agrees.** Translation equivalence mechanics remain INT-R6. |
| INT-R7 supplies key-lifecycle semantics | INT-R7 separates historical signature authenticity from current authorization, preserves predecessor proofs across rotation, and treats uncertain compromise overlap as indeterminate at `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:250-405`. | **Agrees, delivered profile.** Consume; do not redesign. |

## 4. Fixed findings, cited by ID

P36 forbids authority by adjacency. The controlling repository findings are therefore cited by ID,
not by nearby explanatory prose:

- `PV-K01`: current authority is a separately reportable, cutoff-bounded dimension;
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
statement, and a negative/end-to-end semantic test. Its labels and prerequisites are at
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:16-35`.

The prerequisite-sensitive rules used by PAO-R36 are:

- `producer_missing` is legal only where a named consumer already expects an artifact/event but no
  deployed producer emits it;
- `bridge_missing` is legal only where both producer and consumer exist but orchestration does not
  connect them; and
- `verification_missing` is legal only after the chain is wired but lacks an end-to-end automated
  proof.

Therefore:

- the existing public-export producer with no HTTP production caller is `bridge_missing`;
- the absent correction notice/feed/subscriber capability is **absent/unallocated**, not
  `producer_missing`, because no admitted correction consumer contract was found;
- correction-scoped cache and archive fan-out are also **absent/unallocated** until their controlled
  set and consumer obligations are admitted; and
- the full correction chain is not `verification_missing` today because there is no wired chain to
  verify.

## 6. Orientation conclusion

The qualitative asymmetry in the commission brief survives, but several supplied figures do not:
internal supersession is extensively represented while named outward-correction tokens are absent
from connector search; however, the 48/34 supersession file counts are not reproduced, the all-file
`retraction` denominator is seven rather than six, and `rule_evolution.py` has 20 rather than 30
exact top-level declarations.

The correct research posture is not to normalize these discrepancies. It is to bind every later
claim to its precise denominator, mark unavailable literal counts as not established, and avoid any
capability claim from token presence or absence alone.

## 7. `may_not_use_for`

This ledger may not be used for production implementation authorization; a final wire, schema,
package, database, serialization, media-type, or API contract; canonical owner, vendor, or service
appointment; an authority grant; a capability claim; legal sufficiency or a jurisdictional
conclusion; permission to publish or open a gate; or automatic amendment of any plan, backlog, or
system-design decision.
