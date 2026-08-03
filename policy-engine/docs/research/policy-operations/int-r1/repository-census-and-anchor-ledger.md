---
title: INT-R1 — Repository Census and Anchor Ledger
status: delivered
kind: deep-research
research_task: INT-R1
result_type: confirmed
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-amendment
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
amended_after_audit: research/int-r1-independent-audit@0893a739e4739a6cd31dd95bc0b88526e1ff29ae
authoritative_for:
  - repository-level census of existing obligation, confidence-ledger, promotion, assurance, challenge, and projection primitives at the pinned commit
  - correction of the supplied PromotionObligationClass member count at both pinned baselines
  - audited use-sensitive Rule-12 adjudication of the current declared obligation denominator
  - research-level current-capability and reuse-first handoff for INT-R1 consolidation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - current issuance of bounded_complete
  - legal compliance conclusion
  - benchmark passage
  - proof of global obligation completeness
  - authorization to alter, open, dissolve, or dynamically replace PromotionObligationClass
research_only: true
---

# INT-R1 — Repository Census and Anchor Ledger

## 1. Inspection basis and post-audit standing

The original repository inspection was pinned to
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`; the historical Stage-0 baseline was
`4813b49f6ce14e8debf3aaea096f0967d38d9768`. Git comparison established that the former was 121
commits ahead and zero behind the latter. This amendment is pinned to
`978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`, which contains the delivered INT-R1 research, its
independent audit, and downstream registration of the audit's two repository-facing conclusions.
The source anchors below remain the evidence base; the later plan anchors record the accepted
narrowing rather than a new implementation.

The supplied task orientation contained one material factual error. At both the historical and
research baselines, `PromotionObligationClass` has **15** members, not 14. The omitted member was
`VALUE = "value"`. The current definition and its docstring are at
`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235`. This correction is retained exactly:
it is not evidence that the enum recently grew, but evidence that a prose count cannot substitute
for inspection of the pinned source.

Two documents added between the historical and research baselines remain binding:

1. the ratified Stage-0 custody kernel, including the authority-band/candidate-band split,
   fail-closed scope behavior, evidence validity, no-authority-by-passage, and oracle-independence
   constraints (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116`,
   `:164-212`); and
2. the Custody Time Model, separating source effect/publication, PolicyOS receipt, transaction
   visibility, verification, purpose-scoped admission, and PolicyOS publication/lifecycle action,
   with the canonical claim owner choosing the actual reaction
   (`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220`).

Repository instructions require the four-way boundary test and treat time, status, rule version,
provenance, audience, and uncertainty as semantic fields (`AGENTS.md:5-49`, `:68-96`). The
contributor contract requires architecture, quality, testing, and documentation governance for
changes; its cited ranges do **not** independently locate every typed authority contract or
runtime integration owner (`policy-engine/CONTRIBUTING.md:84-139`, `:177-201`). Canonical owners
are therefore anchored in the relevant source files and plans below, not inferred from that
contributor text.

## 2. Obligation denominator and confidence-ledger census

### 2.1 The declared coarse vocabulary has 15 members

At the pinned source the PDC waist declares:

```text
syntax, type, slot, param, coupling, effect, identification, calibration,
measurement, data, implementation, equilibrium, normative, eval_safety, value
```

The adjacent refusal vocabulary includes `single_obligation_fail`,
`joint_obligation_inconsistency`, `proof_timeout`, `scope_insufficient`, and `unknown`; the
per-obligation status vocabulary includes `satisfied`, `failed`, `unknown`,
`scope_insufficient`, and `not_applicable_data_only`
(`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-255`). These are existing fail-closed
destinations. INT-R1 has no justification for a second authority-status lattice.

### 2.2 The ledger is explicit about conditionality

The confidence ledger defines:

```text
P(false promotion | maintained assumptions) <= delta
```

and names the maintained assumptions `obligation_completeness` and `validator_soundness`
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). It requires configured
obligation pools to equal the full declared enum, rejects duplicate or omitted membership as
`obligation_partition_not_total`, and requires pool weights to sum to one
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:337-369`). Roots and receipts
bind policy/schedule identity, obligation split, budget, event-chain material, conditionality, and
maintained assumptions (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:500-1010`,
`:2463-2488`).

The live registry declares the same conditionality, two Basel-square schedules, a 15-class
weighted partition, five proof profiles, and owner/verifier routes
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-89`, `:91-232`). The
five profile kinds are exactly:

- two `ineligible_v1`;
- one `owner_theorem_unavailable_v1`;
- one `deterministic_owner_v1`; and
- one `closed_constant_unit_e_process_v1`.

That distribution is a factual count, not a typed status called “dominated by refusals.” It also
is not a population of missed-obligation observations.

**What is implemented:** total, content-bound risk allocation relative to the declared 15-class
version.

**What is not implemented:** proof that the declared classes, compiler semantics, or compiled
instances exhaust the legal, normative, measurement, implementation, or other obligations that
apply in the world.

### 2.3 N9 makes the declared denominator load-bearing

N9 compiles obligation records, binds eligible confidence-ledger checks, derives refusal reasons,
and sets promotion from those reasons
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:760-1320`). Receipt validation
reconstructs `tuple(PromotionObligationClass)`, rejects mismatch as
`promotion_obligation_denominator_mismatch`, inserts it into refusal reasons, and recomputes the
expected promotion result
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`). A production
receipt with `scope_insufficient` cannot mint authoritative promotion
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:280-340`).

These are strong internal-totality checks. Gate participation, however, does not by itself turn a
governed vocabulary into a Rule-12 defect. The independent audit correctly separated a legitimate
versioned denominator from an unsupported universal-world interpretation.

## 3. Audited Rule-12 adjudication

Organizing Rule 12 permits governed vocabularies, schemas, statuses, ports, and rule versions,
while rejecting hand-maintained enumerations used as substitutes for an open typed capability
path
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:200-222`).
The audited disposition is use-sensitive:

| Use | Rule-12 disposition | Evidence/limit |
| --- | --- | --- |
| Coarse classification for known obligation records | **legitimate governed vocabulary** | Finite versioned categories may support routing, risk strata, rendering, and replay. |
| Exact denominator for one declared compiler/receipt version | **legitimate internal gate** | Equality proves totality relative to that declared version. |
| Evidence that the external obligation world is exhausted | **unsupported/defective interpretation** | An owned denominator does not establish `C_v(B)=U(W)`. |
| Hard boundary preventing an actual source-derived obligation from representation or challenge | **possible Rule-12 defect only with an actual witness** | INT-R1 did not identify such an unrepresentable real obligation. |
| Choice to add a class, extension family, instance layer, or another representation | **not decided by INT-R1** | Research does not authorize a waist change. |

The downstream plan records this exact narrowing as **GY-DEF5**: the defect is the docstring's
claim to be the “Universal N9 obligation-class denominator,” not the existence of the enum. The
plan explicitly says the enum must **not** be opened or dissolved
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`).

The safe research conclusion is therefore:

1. preserve the enum as a versioned coarse vocabulary and declared denominator;
2. never use enum equality or split hashing as proof of world completeness;
3. keep source-derived obligation semantics and unknowns visible outside that internal-totality
   proposition;
4. preserve challenge and governed amendment paths; and
5. do not select a future representation from this research file.

## 4. P29 stopping point and the boundary of transfer

P29 permits stopping the verifier regress when a mechanism derives its check set generically from
the actual owned source of truth, walks it recursively, and permits only genuine typed exemptions
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`; `AGENTS.md:39-49`).
That stopping point transfers to:

- every field and nested object in an owned schema;
- every entry in a fixed immutable basis artifact;
- every route in a governed validator registry;
- every class in a declared denominator version; and
- every future owned-object addition that the generic traversal necessarily reaches.

It does not prove that the selected external basis contains every applicable source or obligation.
The external world is not one complete PolicyOS object graph. The defensible separation is:

1. mechanical closure over what PolicyOS owns;
2. governed evidence and challenge about source competence, scope, and semantic adequacy; and
3. explicit unknown remainder for what is not closed.

The first may be complete-by-construction. The second remains evidential/institutional. The third
remains open wherever an unseen decisive extension is admissible.

## 5. Existing primitives and audited gaps

| Primitive | Existing contribution | INT-R1 gap | Anchor |
| --- | --- | --- | --- |
| PDC classes/statuses | coarse vocabulary and fail-closed outcomes | no source universe, instance coverage, exclusions, remainder, TTL, or challenge artifact | `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-255` |
| Confidence ledger | strict risk partition, receipts, event chain, typed maintained assumptions | no evidence that compiler completeness or validator soundness holds | `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`, `:500-1010` |
| N9 promotion sequence | compiles/consumes class-level obligation records and recomputes promotion | no coverage envelope, independent source oracle, or pre-class instance layer | `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:760-1900` |
| Formal invariants | property/owner/evidence/revisit/negative-test structure | no INT-R1 open-world coverage invariant or independent external oracle | `policy-engine/src/polisyos/runtime/quality/formal_invariants.py:23-105`, `:145-158` |
| Assurance case | claim/evidence/assumption/defeater/blocker structures and projections | structures an argument but cannot discover a missing world obligation | `policy-engine/src/polisyos/runtime/quality/assurance_case.py:1-60`, `:120-173` |
| Candidate firewall | prevents candidate content filling protected authority slots | does not decide external applicability | `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-73` |
| Evidence spine and claim registry | bind provenance, norms, limitations, blockers, uncertainty | no current INT-R1 envelope/governance binding | `policy-engine/src/polisyos/runtime/quality/evidence_spine.py:1-125`; `policy-engine/src/polisyos/runtime/quality/claim_registry.py:1-107` |
| Grounding bind | revalidates local grounding references and obligations | local grounding closure is not world discovery | `policy-engine/src/polisyos/runtime/quality/grounding_bind.py:1-121` |
| Acquisition planner | routes typed data/legal-corpus/competence gaps | no complete open-world obligation discovery producer | `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:1-190` |
| CTM/N12 patterns | receipt, verification, admission, perturbation, reissue distinctions | no complete INT-R1 challenger-to-claim bridge | `policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220` |
| Atlas laws/plans | one lattice, immutable history, unknown/blocked projections, DS12/DS17/DS18 consumers | no owner-produced positive coverage value; DS17 now treats unresolved as steady state | `policy-engine/docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md:130-260`; `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` |

### 5.1 GY-GAP1: current representation cannot execute OM-01

`PromotionObligationRecord` carries a coarse `obligation_class` and `gate_id`; current N9 creates
one record per enum class. It has no source-derived obligation-instance identity or pre-class
aggregation layer. The mandatory INT-R1 deletion fixture requires two instances in one class,
removal of one, and preservation of the class row. The downstream plan registers this as
**GY-GAP1** and states that OM-01 cannot execute today
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:7`).

This is a missing capability, not evidence that the enum must be opened. A future design would
need a pre-aggregation instance collection, semantic instance identity, an instance-to-class
bridge, and an independent comparison point. INT-R1 does not freeze those shapes.

### 5.2 Independence is specified but not constructed

The repository has no admitted independent source-to-obligation checker/scorer, no complete
validator-governance producer, no coverage-envelope producer, and no N9/N11 bridge. S0-GAP-02
remains the independent-oracle/scoring dependency. An `independence_record` populated by the
producer cannot close this gap. Atlas Revision 3.10 therefore treats `open_world_unresolved` as
the honest current steady state rather than a placeholder
(`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7`).

## 6. Current capability labels

| Capability slice | Current label | Limitation |
| --- | --- | --- |
| δ arithmetic, event chain, spend, and conditionality | `implemented` | mathematical result remains conditional |
| Totality over declared 15-class denominator | `implemented_relative_to_enum` | no world-completeness implication |
| World-level obligation discovery | `producer_missing` | no source can prove absence of unseen obligations generally |
| Per-scope closure-premise disposition | `contract_missing` | research semantics only |
| `ObligationCoverageEnvelope` | `contract_missing` | no canonical runtime/PDC artifact |
| `ValidatorGovernanceRecord` | `contract_missing` | adjacent owner fields are not a complete governance capability |
| Independent source-to-obligation checker/scorer | `producer_missing` | S0-GAP-02 unresolved |
| Obligation-instance/aggregation layer | `producer_missing` / `GY-GAP1` | OM-01 not executable |
| Mutation/metamorphic battery | `semantic_test_missing` | no implemented or scored INT-R1 suite |
| Challenger intake to canonical reaction | `bridge_missing` | patterns exist, end-to-end chain absent |
| Public conditional projection | `consumer_waiting` | DS17 must currently render unresolved, not fabricate a value |
| `bounded_complete` issuance | **unavailable** | independence and complete capability chain absent |

The aggregate INT-R1 standing is **research-only/contract-only**. Any attempted current protected
use maps to `open_world_unresolved` and an existing fail-closed status.

## 7. Reuse-first handoff

| Concern | Existing home to prefer | Research disposition |
| --- | --- | --- |
| Coarse class vocabulary/statuses | PDC waist | preserve; no INT-R1-authorized enum redesign |
| Substantive obligation compilation/promotion reaction | N9 | extend only after GY-GAP1 and consolidation |
| Conditional ledger binding | N11 | reference admitted coverage/governance evidence; no parallel risk ledger |
| Generic mechanical checks | formal invariants and receipt validators | reuse P29 traversal/negative patterns; do not call same-path recomputation independent |
| Assumptions/defeaters/limitations | assurance case, claim registry, evidence spine | wire/extend existing owners |
| Gap routing | acquisition planner plus INT-R2 | extend without reducing non-data gaps to rows |
| Expiry/perturbation/reissue | N12/CTM and canonical claim owner | preserve owner-controlled append-only reaction |
| Projection | Atlas DS12/DS17/DS18 | render only; unresolved is current steady state |
| Independent oracle/scoring | S0-GAP-02 | unresolved external dependency, not self-attested metadata |

No current file establishes a standalone obligation-coverage authority. Research does not appoint
one.

## 8. Boundary verdict

| Plane | Verdict | Boundary implication |
| --- | --- | --- |
| PolicyOS statement about its own search, compilation, checks, exclusions, remainder, and current standing | **OWN** | PolicyOS owns truth, expiry, challenge, correction, supersession, and replay of what it signs. |
| External legal/normative/measurement/implementation facts and competence | **INTEGRATE** | PolicyOS owns typed receipt/admission/reaction, not the external function. |
| Unadmitted source signals or challenger allegations | **OBSERVE** | may trigger acquisition/review; mint no pass or authority |
| Lawmaking, final adjudication, service/payment/remedy execution | **OUT_OF_SCOPE** | typed evidence and notification only |

## 9. Empirical baseline and scoped wording

At the **pinned W12.D/G5 proving-ground snapshot**, 13 cases remain typed blockers, with zero
grounded conversions and zero useful-design credit. The supporting plan/manifest establish that
snapshot; they do not prove that no unrelated experimental invocation ever occurred in repository
history. The live profile registry is likewise not a set of missed-obligation observations.
Consequently:

- no frequentist miss rate is presently estimable from positive governed promotions;
- a numeric probability of an unknown remainder would be authored rather than calibrated; and
- future challenger yield, source latency, reviewer disagreement, mutation survival, TTL breach,
  and reissue frequency may improve governance without proving world closure.

## 10. Pattern and negative-finding disposition

| Pattern | Audited standing |
| --- | --- |
| P01 contract-only capability | confirmed: producers/bridges are missing |
| P04 parallel status lattice | prohibited: coverage assessments only feed the existing lattice |
| P05 authority dilution | public δ rider must remain relative and expose remainder/currentness |
| P10 structural completeness | enum/partition totality is not semantic/world completeness |
| P13 governance gravity | extend N9/N11/N12/claim owners; do not invent a parallel service from research |
| P14 independence inflation | a second function name or shared-path replay is not independence |
| P29 authorial proof | producer-filled diligence fields cannot establish bounded coverage |
| P31 instance patching | do not respond to each miss merely by adding a class; preserve governed source/instance semantics |
| P32 trust by form | hashes/fields must resolve to competent, current evidence |
| P33 teaching to test | fault suites require variants and an independent oracle |

### Confirmed negative findings after audit

1. The repository proves internal totality relative to a closed 15-class version, not global
   obligation completeness.
2. The enum is a legitimate governed denominator; only its universal-world interpretation is
   defective without further evidence.
3. P29 closes mechanical traversal regress over owned sources, not external source selection.
4. No empirical history calibrates unknown-obligation probability.
5. No implemented envelope, governance record, independent scorer, instance layer, or complete
   challenger-to-reissue chain exists.
6. Current `bounded_complete` issuance is unavailable; `open_world_unresolved` is the honest
   fail-closed standing.
7. Existing owners and statuses are sufficient to avoid a parallel lattice, but not yet a
   complete INT-R1 capability.

These findings support `accepted_narrow_scope`: a conditional inclusion protocol is a viable
research result; universal open-world completeness and current positive capability are not.
