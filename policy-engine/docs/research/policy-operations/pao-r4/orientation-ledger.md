---
title: PAO-R4 — Orientation ledger
research_id: PAO-R4
artifact_role: orientation-ledger
status: amended_research
research_only: true
repository: DenisKopylov/polisyos
audited_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
audit_commit: 69182c079fb5dc99808d7cd27874d50433efd5a4
pinned_repository_commit: 109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee
source_equivalent_original_pin: 1a7a2d05ebba22fae80e9934329e4b880806588e
result_standing: GO_WITH_REVISIONS
adoption_status: NO_GO_pending_independent_conformance
authoritative_for:
  - amended research orientation at the pinned repository state
  - architecture-supplied complete-tree source vocabulary census
  - research-only owner and boundary identification
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
---

# PAO-R4 orientation ledger

## 1. Pin, source identity, and count vocabulary

The controlling documentation pin is
`109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`. The architecture principal established that
`policy-engine/src` is byte-identical at that commit and the original PAO-R4 pin
`1a7a2d05ebba22fae80e9934329e4b880806588e`; the intervening delta is documentation only.
Repository citations below use `109ba3f4` for documentation and may use the same pin for source
because the source bytes are identical.

Every census states two denominators:

- **path denominator** — the root walked, here `policy-engine/src` unless narrowed explicitly;
- **file-type denominator** — either every non-binary source file or Python files only.

The measured units remain distinct:

- **token-containing files** — distinct paths containing one or more matches;
- **matching lines** — physical source lines containing one or more matches;
- **occurrences** — non-overlapping matches, so a line may contain more than one occurrence.

This applies the `P35` index rider: an index is not a denominator in either direction. The settled
figures in §3 come from the architecture principal's complete tree walk using `git grep` over the
pinned ref, binary files excluded. They are recorded rather than re-derived in this amendment, as
directed. `P36` continues to require finding IDs instead of authority by adjacent prose, and `P37`
requires provenance classification of every gate predicate. See
`policy-engine/docs/reference/policy-design-case-failure-patterns.md:79-81@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, findings `P35`, `P36`, and `P37`.

## 2. Binding architecture and file sizes

| Repository claim | Unit | Result | Pinned evidence | Disposition |
|---|---|---:|---|---|
| `public_export.py` | physical source lines | 2,103 | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |
| `projection_semantics.py` | physical source lines | 3,763 | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |
| public-verification ratification | physical source lines | 439 | `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md:434-439@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |
| Stage-0 ratification | physical source lines | 264 | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:258-264@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |
| INT-wave ratification | physical source lines | 379 | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:373-379@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |
| canonical projection audiences | enum members | 4: `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE` | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:648-655@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee` | confirmed |

The identity ruling remains controlling: PolicyOS owns the individual-decision firewall but not the
individual decision. See
`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:101-139@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`, finding **Individual-decision firewall**. The
Stage-0 authority-band lens at
`stage0-custody-kernel-ratification.md:46-88@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`
and its binding application note at `:164-176` prohibit authority leakage without prohibiting
candidate-band computation or transport.

## 3. Complete source vocabulary census — settled figures

### 3.1 Complete table

Search method: complete tree walk at the pin; path denominator `policy-engine/src`; fixed,
case-sensitive strings except the explicitly case-insensitive `anonymi` prefix; binary files excluded.

| Token/family | Path denominator | File-type denominator | Files | Matching lines | Occurrences |
|---|---|---|---:|---:|---:|
| exact `may_not_use_for` | `policy-engine/src` | Python only | **106** | **794** | **903** |
| exact `may_not_use_for` | `policy-engine/src` | all non-binary source files | **106** | not separately supplied | not separately supplied |
| case-insensitive prefix `anonymi` | `policy-engine/src` | all non-binary source files | **7** | not separately supplied | not separately supplied |
| case-insensitive prefix `anonymi` | `policy-engine/src` | Python only | **6** | not separately supplied | not separately supplied |
| exact `aggregate_only` | `policy-engine/src` | all non-binary source files | **7** | not separately supplied | not separately supplied |
| exact `individual_decision` | `policy-engine/src` | all non-binary source files | **0** | **0** | **0** |
| exact `export_gate` | `policy-engine/src` | all non-binary source files | **0** | **0** | **0** |
| exact `prohibited_use` | `policy-engine/src` | all non-binary source files | **0** | **0** | **0** |

The dash-like omissions in the supplied all-source positive rows are preserved as “not separately
supplied”; no Python matching-line or occurrence count is silently relabelled as all-source.

### 3.2 Disjoint `may_not_use_for` partition

The 106 token-containing Python files form three disjoint path sets:

| Partition | Path predicate | Files |
|---|---|---:|
| runtime | below `policy-engine/src/polisyos/runtime/` | **67** |
| scientist | below `policy-engine/src/polisyos/scientist/` | **12** |
| remainder | Python files below `policy-engine/src/polisyos/`, excluding both roots | **27** |
| **union** | three mutually exclusive predicates | **106** |

The partition is disjoint by path construction and `67 + 12 + 27 = 106`. The denominator is the
complete exact-token Python hit set, not every Python file in the repository.

### 3.3 `aggregate_only` hit set

The seven all-source token-containing paths are:

1. `policy-engine/src/polisyos/fabric/evidence/decision_data.py`;
2. `policy-engine/src/polisyos/runtime/quality/capability_index.py`;
3. `policy-engine/src/polisyos/runtime/quality/semantic_fixtures.py`;
4. `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py`;
5. `policy-engine/src/polisyos/runtime/quality/capability_index_compiler.py`;
6. `policy-engine/src/polisyos/runtime/quality/design_axes/substrate_acquisition.py`;
7. `policy-engine/src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py`.

These uses are form, redaction, rights-envelope, and fixture-visibility metadata. They do not prove
cross-release non-resolution or downstream individual-use control.

### 3.4 `anonymi` hit set and the corrected denominator

The six Python paths are:

1. `policy-engine/src/polisyos/core/security/authz.py`;
2. `policy-engine/src/polisyos/scientist/methods/search/transfer_context.py`;
3. `policy-engine/src/polisyos/fabric/catalog/contract.py`;
4. `policy-engine/src/polisyos/runtime/http/authz_middleware.py`;
5. `policy-engine/src/polisyos/scientist/governance/passes/pii_check_pass.py`;
6. `policy-engine/src/polisyos/data_forge/_impl/compliance.py`.

The seventh all-source path is:

`policy-engine/src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_block_context_sociocultural.csv`.

It contains the case-insensitive prefix in `anonymity`. The original six-file result was a Python
count presented under an all-source denominator. The amended statement is seven all-source and six
Python, with both denominators explicit.

### 3.5 Zero-result searches

The exact all-source searches for `individual_decision`, `export_gate`, and `prohibited_use` each
produce zero files, zero matching lines, and zero occurrences. The walk that produced them was
executed by the architect at pin `109ba3f44` and independently reproduced there with positive and
negative controls, so the **numbers are sound**; the original refusal to infer a zero from a connector
index also stands.

What this package may do with them is narrower. Its own environment could not execute a complete
tree walk, so under ratified `W4-K01`
(`docs/system-design-decisions/wave4-decision-evidence-ratification.md`) the census is
`institutionally_supplied` **to this package**, and an `institutionally_supplied` census **cannot
settle a zero**. These are therefore recorded as reproducible claims, not as established absences of
this package. The earlier wording — "settled true zeroes from a complete walk" — asserted an
entitlement this package does not hold, and is corrected here rather than removed: nothing about the
measurement was wrong, only about who may cite it.

The negative capability conclusion does **not** rest on these zeroes and is unchanged by the
correction: it rests on the absence of an admitted typed chain, producer, persisted artifact, bridge,
consumer, verification and appointed owner, which the integration handoff establishes independently.
On that basis the source can carry denied uses
but cannot name an individual-decision concept, a policy-to-case export gate, or a parallel
`prohibited_use` mechanism.

## 4. Existing live mechanism

The reusable primitive has three bounded operations:

1. authority envelopes declare `may_not_use_for`;
2. producer/projection paths propagate or union restrictions; and
3. consumer guards reject a denied purpose or a purpose absent from `authoritative_for`.

Representative anchors are:

- `policy-engine/src/polisyos/core/contracts/runtime.py:278-329@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`;
- `policy-engine/src/polisyos/policy_grammar/_impl/authority.py:17-55@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`;
- `policy-engine/src/polisyos/policy_grammar/_impl/consumer.py:53-67@109ba3f44e09e0d34cf49ae19aa25ba4048ee3ee`.

`PV-K04` already ratifies that denied uses do not shrink under projection. PAO-R4 instantiates that
property for individual-use purposes; it does not create a second prohibition mechanism or re-ratify
the invariant.

## 5. Boundary owners and open placement

The following ownership claims are established:

- authority-purpose and denied-use carriers belong to existing core contracts and bounded consumers;
- projection semantics and denial monotonicity belong to the existing projection owner;
- Fabric/runtime authorization sources may supply access and redaction facts but cannot turn an
  anonymization label into firewall permission.

The following ownership claim is **not** established:

- `public_export.py` is a real producer of a public redacted bundle, but no pinned finding appoints it
  as the canonical chokepoint for every non-public, purpose-bound case-system handoff.

Under `P36`, the policy-to-case emission chokepoint remains an open consolidation decision. This
research appoints no owner and creates no implementation. The PAO-R4-specific chain remains
**`absent/unallocated`**.

## 6. Orientation conclusion

1. The central source shape is confirmed in full: 106 exact-token Python files, 794 matching lines,
   903 occurrences, and the disjoint 67/12/27 partition.
2. `aggregate_only` appears in seven all-source files and remains form metadata, not a firewall.
3. `anonymi` appears in seven all-source files and six Python files; neither count establishes
   non-resolution.
4. The three missing-vocabulary searches return zero on an architect-executed complete all-source
   walk. That census is `institutionally_supplied` to this package, so under `W4-K01` the zeroes are
   recorded as reproducible claims and **not** as established absences of this package; the negative
   capability conclusion rests on the missing chain (item 6), not on them.
5. The live denied-use mechanism is reusable and pervasive.
6. The individual-decision vocabulary, gate, governed case consumer, evidence return, and
   composition transcript remain absent/unallocated.
7. No source capability or canonical handoff owner is upgraded by this amendment.
