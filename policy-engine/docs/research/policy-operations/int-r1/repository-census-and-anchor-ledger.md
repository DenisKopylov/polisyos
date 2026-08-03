---
title: INT-R1 — Repository Census and Anchor Ledger
status: delivered
kind: deep-research
research_task: INT-R1
result_type: confirmed
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r1-obligation-coverage
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - repository-level census of existing obligation, confidence-ledger, promotion, assurance, challenge, and projection primitives at the pinned commit
  - correction of the supplied PromotionObligationClass member count at both pinned baselines
  - research-level Rule-12 adjudication of the current closed obligation denominator
  - candidate reuse-first owner map for later INT-R1 consolidation
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - legal compliance conclusion
  - benchmark passage
  - proof of global obligation completeness
research_only: true
---

# INT-R1 — Repository Census and Anchor Ledger

## 1. Inspection basis and correction to the supplied context

This ledger records repository facts at the required pinned commit,
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`, and distinguishes them from the historical
Stage-0 baseline, `4813b49f6ce14e8debf3aaea096f0967d38d9768`. Git comparison reports the current
commit as 121 commits ahead of the historical commit and zero commits behind. The current
research branch was created from the exact current commit; no older Stage-0 report is used as
a substitute for direct inspection.

The supplied task context contains one material factual error: the closed denominator is not a
14-member enum. At both the historical and current pinned commits,
`PromotionObligationClass` contains **15** members, because `VALUE = "value"` is present after
`EVAL_SAFETY`. The current definition and its “Universal N9 obligation-class denominator”
docstring are at
`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-235`; the historical definition has the
same 15 members. This is not evidence that the universe has recently grown from 14 to 15. It
is evidence that the task's orientation note omitted a member and that an auditor must derive
the denominator from the pinned source rather than a prose count.

Two current-baseline additions materially change the research frame relative to the historical
commit:

1. the ratified Stage-0 custody kernel now exists and binds the authority-band/candidate-band
   distinction, fail-closed scope behavior, evidence validity, and bounded-passage rule
   (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:43-116`,
   `:164-212`); and
2. the adopted Custody Time Model now separates source occurrence/effect/publication, PolicyOS
   receipt, verification, purpose-scoped admission, and PolicyOS publication/lifecycle action,
   and requires the claim owner—not a transported payload—to choose the actual reaction
   (`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-145`,
   `:146-220`).

Neither document exists at the historical pinned commit. Their presence at the current commit
means INT-R1 must design an append-only challenge/reissue protocol and cannot treat a coverage
status as a timeless field on a mutable promotion record.

Repository instructions reinforce the same boundary: PolicyOS owns what it signs, must use the
four-way boundary test, must treat time/status/rule/provenance/audience as load-bearing, and must
not turn an unresolved research question into a code contract (`AGENTS.md:5-37`, `:68-96`).
The contributor contract also locates typed authority contracts and runtime integration under
existing architecture governance rather than authorizing a new subsystem from a research file
(`policy-engine/CONTRIBUTING.md:84-139`, `:177-201`).

## 2. Obligation denominator and confidence-ledger census

### 2.1 Closed class denominator

At the current baseline, the canonical PDC waist declares these 15 coarse classes:

```text
syntax, type, slot, param, coupling, effect, identification, calibration,
measurement, data, implementation, equilibrium, normative, eval_safety, value
```

The adjacent fail-closed reasons are `single_obligation_fail`,
`joint_obligation_inconsistency`, `proof_timeout`, `scope_insufficient`, and `unknown`, and the
per-obligation status vocabulary contains `satisfied`, `failed`, `unknown`,
`scope_insufficient`, and `not_applicable_data_only`
(`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-255`). These statuses already provide
existing destinations for incomplete or unresolved coverage evidence. INT-R1 therefore has no
justification for creating a second authority-status lattice.

### 2.2 Totality is implemented relative to the enum

The confidence ledger is unusually explicit about its conditionality. It defines the public
mathematical clause as:

```text
P(false promotion | maintained assumptions) <= delta
```

and states that the clause is conditional on `obligation_completeness` and
`validator_soundness`; both are carried as typed maintained assumptions
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`). The ledger registry
then requires the configured obligation pools to equal the full set of
`PromotionObligationClass`, rejects duplicates or omissions as
`obligation_partition_not_total`, and requires pool weights to sum exactly to one
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:337-369`). The immutable root
and receipt bind the split hash, policy/schedule hashes, budget, conditionality clause, and
maintained assumptions into the durable artifact
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:500-1010`, `:2463-2488`).

The live registry mirrors that structure. It declares the same conditionality, two
Basel-square schedules, a 15-class weighted partition, five proof profiles, and the owner and
verifier routes for currently admitted certificate classes
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-89`, `:91-232`). The
five profiles are not an empirical history of real positive promotions: one is a genuine
closed-constant-unit e-process, one records an unavailable owner theorem, one is deterministic,
and two are ineligible profiles (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-89`).

**Repository fact proved:** the ledger has a checkable, content-bound, total risk allocation
relative to the 15-class enum.

**Repository fact not proved:** the 15 classes, or the obligation instances compiled beneath
them, exhaust every legal, normative, measurement, implementation, or other obligation that
actually applies in the world.

### 2.3 The promotion gate makes the enum capability-gating

The N9 sequence does more than display the class vocabulary. It compiles obligation records,
binds eligible confidence-ledger checks to those records, derives refusal reasons, and sets
`promoted = not refusal_reasons`
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:760-1320`). Its receipt
validator independently reconstructs the denominator and requires the ordered obligation-class
tuple to equal `tuple(PromotionObligationClass)`; a mismatch becomes
`promotion_obligation_denominator_mismatch`, is inserted into refusal reasons, and changes the
expected promotion result (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1320-1900`).
A promoted receipt also requires a derivation trace, and a `scope_insufficient` obligation may
not mint an authoritative production promotion
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:280-340`).

The exact-totality checks are useful and should be preserved for what they actually establish:
no currently declared class was silently dropped from a compiled promotion receipt or the risk
split. They also establish that the enum is **currently a capability-gating enumeration**, not
merely a descriptive vocabulary. Removing a member changes whether a candidate may promote;
adding a member creates a mandatory denominator row; exact class equality is a gate condition.

## 3. Rule 12 adjudication

Organizing Rule 12 distinguishes two categories:

- governed vocabularies, schemas, statuses, ports, and rule versions may be finite and versioned;
- hand-maintained enumerations that determine what capability exists are defects, because
  capability must follow a typed corpus/search path and new admissible resources should not
  require hardcoded code changes
  (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:200-222`).

The present `PromotionObligationClass` falls on both sides depending on the claim made about it:

| Use | Rule-12 verdict | Reason |
| --- | --- | --- |
| Coarse classification/tag for known obligation instances | legitimate governed vocabulary | A finite vocabulary can aid routing, budgeting, rendering, and stable rule references. |
| Exact list of classes a receipt must represent | legitimate only as a denominator for the declared compiler version | It proves internal totality relative to that version, not external completeness. |
| Universal set of every obligation kind that can ever matter | defect / unsupported capability claim | It gates promotion while lacking a corpus/search/amendment path that can discover world obligations without code changes. |
| Evidence that `obligation_completeness` is discharged | refuted | Exact equality to a self-declared enum proves only equality to that enum. |

Accordingly, INT-R1 does **not** recommend deleting the enum. The research-level disposition is
narrower:

1. preserve it as a versioned, amendable, coarse governed classification;
2. stop treating it, its partition, or its split hash as the obligation universe;
3. require obligation **instances** to be derived from a declared closure basis and bound to
   source, rule, scope, time, and provenance;
4. preserve extension/unknown categories and a challenge path without converting them into an
   automatic pass; and
5. make every public δ statement relative to the declared obligation set and its coverage
envelope.

This adjudication is a research result, not an authorization to change the enum, its members,
the current denominator, its weights, or any production gate.

## 4. P29 stopping point: what transfers and what does not

The repository's P29 stopping point is sound for a verifier whose actual source of truth is
owned and inspectable: derive checks from the runtime's real rejection reasons, schema fields,
or actual objects; walk them generically; permit only genuine type-constrained exemptions; then
use that generic rule plus review rather than an infinite verifier-of-verifier tower
(`policy-engine/docs/reference/policy-design-case-failure-patterns.md:70-75`; `AGENTS.md:39-49`).

The move transfers to these INT-R1 subproblems:

- proving that every obligation instance in a declared artifact was visited;
- proving that every class in a declared compiler version was represented;
- proving that every source entry in a fixed closure-basis snapshot was processed;
- proving that every validator route in a governed registry was independently exercised; and
- proving that no future schema field can evade a generic recursive traversal, subject to
  genuine typed exemptions.

It does **not** transfer to discovery of the world-level obligation universe. The actual source
of truth for legal, normative, measurement, and implementation obligations is not a PolicyOS
schema. It spans competent lawmakers, courts, regulators, institutions, contracts, local
practice, affected-person claims, measurement regimes, and implementation facts. A generic
walk over PolicyOS objects cannot prove that an unobserved external source or unarticulated norm
does not exist.

The defensible stopping point is therefore three-layered rather than recursive:

1. **mechanical closure proof** over a declared, immutable closure basis;
2. **independent governance and challenge** over whether that basis was competent, current,
   scoped, and diligently selected; and
3. **an explicit unknown remainder** outside the basis, with fail-closed effect on affected
   protected actions and a typed path for acquisition, challenge, and reissue.

Layer 1 can be complete-by-construction. Layers 2 and 3 remain institutional and open-world.
Calling layer 1 “world complete” would simply rename the regress.

## 5. Existing primitives relevant to INT-R1

| Existing primitive | What it already proves or carries | What remains missing for INT-R1 | Repository anchor |
| --- | --- | --- | --- |
| `PromotionObligationClass` and `PromotionObligationStatus` | Stable coarse classes and fail-closed per-obligation outcomes | Declared source universe, obligation-instance discovery, exclusions, unknown remainder, TTL, challenge | `policy-engine/src/polisyos/pdc/_impl/gy_waist.py:218-255` |
| Confidence ledger root/receipt | Immutable risk policy, split hash, event chain, spend, maintained assumptions | Evidence that `obligation_completeness` and `validator_soundness` hold | `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:37-50`, `:500-1010` |
| N9 promotion sequence | Compiles obligations, binds owner checks, recomputes receipt, fails closed | Coverage envelope and independent coverage decision are not gate inputs | `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:760-1900` |
| Formal invariant registry | Named properties, owners, accepted check types, model properties, evidence, revisit triggers, negative tests | No registered invariant for open-world obligation coverage; no external closure oracle | `policy-engine/src/polisyos/runtime/quality/formal_invariants.py:23-105`, `:145-158` |
| Assurance case | Claim/evidence/assumption/defeater/blocker/confidence-limit structure, including SACM/CAE mappings | It structures a coverage argument but does not discover omitted obligations | `policy-engine/src/polisyos/runtime/quality/assurance_case.py:1-60`, `:120-173` |
| Candidate firewall | Prevents candidate content from filling protected authority slots, including obligation authority | Does not determine which external obligations exist | `policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-73` |
| Evidence spine | Carries requirement IDs, producer/read contracts, authority profile, schema/code revision, input/output refs | Needs coverage-envelope and challenge refs, if later adopted by canonical owners | `policy-engine/src/polisyos/runtime/quality/evidence_spine.py:1-125` |
| Claim registry | Binds claims to scenario, data, norms, methods, arguments, counterevidence, limitations, deficits, authority blockers, uncertainty | No obligation-coverage envelope or validator-governance binding currently visible | `policy-engine/src/polisyos/runtime/quality/claim_registry.py:1-107` |
| Grounding bind gate | Revalidates candidate relation certificates against the live reference and blocks open obligations | Open obligations are local grounding obligations, not proof of world obligation discovery | `policy-engine/src/polisyos/runtime/quality/grounding_bind.py:1-121` |
| Acquisition planner | Routes typed evidence gaps before VOI and represents legal corpus/competence and limitation routes; records do not themselves satisfy evidence | No generic non-data obligation-discovery case yet; INT-R2 may generalize this | `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py:1-190` |
| Custody Time Model | Separates receipt, verification, admission, publication, and lifecycle action; defines owner-controlled late-event reaction | No obligation-specific challenger producer/state machine implemented | `policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:1-220` |
| Atlas status/surface laws | One status lattice, immutable closed cases, typed unknown/blocked/outside-envelope states, no UI-minted authority | DS12/DS17/DS18 are consumers waiting for an INT-R1 input | `policy-engine/docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md:130-260`; `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7` |

## 6. Current capability labels

The capability-reality labels below describe the pinned repository. They do not authorize a
repair.

| Capability slice | Current label | Evidence and limitation |
| --- | --- | --- |
| δ arithmetic, event chain, spend, and conditionality | `implemented` | The ledger is strict and content-bound, but the theorem remains conditional (`confidence_ledger.py:37-50`, `:500-1010`). |
| Totality over declared 15-class denominator | `implemented_relative_to_enum` | Exact set/tuple checks exist (`confidence_ledger.py:337-369`; `promotion_sequence.py:1320-1900`). |
| World-level obligation discovery/completeness | `producer_missing` | No producer can prove the absence of unobserved world obligations. |
| `ObligationCoverageEnvelope` | `contract_missing` | No matching canonical runtime/PDC artifact was found. The backlog names a research output only (`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:260-500`). |
| `ValidatorGovernanceRecord` | `contract_missing` | Owner/verifier fields exist in adjacent records, but no obligation-validator governance record exists as a complete capability. |
| Independent obligation-coverage validator | `producer_missing` | Existing receipt validation recomputes from the same closed denominator; it does not independently test source-to-obligation coverage. |
| Mutation/metamorphic obligation fault battery | `semantic_test_missing` | Existing negative machinery is reusable, but the decisive-obligation and validator-fault tests required by INT-R1 are not present as implemented tests. |
| Challenger intake and independent disposition | `bridge_missing` | Assurance-case defeaters and CTM lifecycle concepts exist, but no complete challenger producer→event→claim reaction chain was found. |
| Suspend/reissue/supersede on accepted challenge | `implemented_but_not_orchestrated` at pattern level | Existing lifecycle vocabulary and CTM rules are strong; an INT-R1-specific producer/bridge is missing. |
| Public δ conditional chip | `consumer_waiting` | Atlas plans DS12/DS17/DS18 as consumers and explicitly bind them to INT-R1, but the producer contract is not implemented (`POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7`). |

The smallest honest aggregate label is therefore **`contract_only` for the proposed INT-R1
coverage capability**, despite mature adjacent components. A strict δ ledger is not an
obligation-coverage producer; a planned UI chip is not a coverage surface; an assurance-case
node is not a source census; and a typed assumption is not its discharge.

## 7. Reuse-first canonical-owner map

This map identifies existing owners a later consolidation or implementation plan could extend.
It does not establish a new canonical owner.

| INT-R1 concern | Existing owner to prefer | Research disposition | Reason |
| --- | --- | --- | --- |
| Coarse obligation-class vocabulary and per-obligation outcome | PDC waist / `gy_waist.py` | `extend-existing` only after consolidation | Preserve one narrow waist and one status lattice; do not create a second denominator. |
| Obligation instance compilation and promotion reaction | N9 / `promotion_sequence.py` | `extend-existing` | It already compiles and consumes obligation records and owns the promotion decision. |
| Conditional δ receipt and maintained-assumption binding | N11 / `confidence_ledger.py` | `extend-existing` | Add a coverage/governance reference only if later ratified; do not create a parallel risk ledger. |
| Generic invariant and independent recomputation patterns | `formal_invariants.py` and existing receipt validators | `extend-existing` | Reuse property/revisit/negative-test machinery, but require an oracle independent of the fault being tested. |
| Defeaters, assumptions, unresolved uncertainty | `assurance_case.py` | `wire-existing` | Coverage arguments and challenges can be projected into the existing assurance case. |
| Claim-local evidence, limitations, blockers | `claim_registry.py` and `evidence_spine.py` | `extend-existing` | Bind a future envelope to affected claims instead of inventing a parallel claim registry. |
| Gap acquisition and unavailable owner/source routes | `acquisition_planner.py` plus INT-R2 consolidation | `extend-existing` / `candidate_for_consolidation` | Reuse typed gap routing; do not pretend row acquisition closes mandate or normative gaps. |
| Epoch, expiry, perturbation, revalidation, reissue | GY-N12 and the adopted Custody Time Model | `extend-existing` | A missed obligation is a material perturbation; historical artifacts remain immutable. |
| Public/reviewer/machine projection | Atlas DS12/DS17/DS18 | `wire-existing` after producer exists | Atlas renders coverage and currentness; it never decides either. |
| Independent benchmark oracle | S0-GAP-02 and INT-R9 | `external_dependency_assumption` | Same-code self-recomputation cannot prove semantic coverage or first-promotion validity. |

No current file establishes a standalone “obligation coverage authority” owner. Creating a
new service or status family would violate the reuse-first and one-lattice rules unless later
consolidation proves that no existing owner can carry the concern. The narrowest visible path is
an immutable coverage artifact referenced by N9/N11, lifecycle-managed through N12/CTM, bound to
claims through existing registries, and projected by Atlas.

## 8. Boundary verdict

| Plane | Verdict | Owner/boundary implication |
| --- | --- | --- |
| PolicyOS statement about what it searched, compiled, checked, excluded, and still does not know | **OWN** | If PolicyOS publishes the coverage statement, it owns its truth, expiry, challenge, correction, supersession, and historical reconstruction. |
| External legal/normative/measurement/implementation source production and competence | **INTEGRATE** | PolicyOS owns typed receipt, verification, admission, and reaction; it does not become legislator, regulator, court, measurement authority, delivery operator, or institutional norm owner. |
| Source-owner succession, institutional context, newly emerging concerns, horizon signals | **OBSERVE** until admitted | They may trigger acquisition or challenge but cannot silently mint an obligation or a pass. |
| Making law/norms, deciding external legal effect, executing service/payment/remedy/rollback | **OUT_OF_SCOPE** | INT-R1 may specify evidence and reaction contracts, never external sovereign action. |

This follows the ratified four-way test and signature rule
(`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:52-145`).

## 9. Empirical baseline and its hard limit

The repository does not supply a defensible empirical base rate for missed obligations in real
positive governed promotions. The live registry is dominated by deterministic, ineligible, or
owner-unavailable profiles rather than a population of real positive decisions
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-89`). The active
plans still treat the first governed promotion as a gated future event and require INT-R1 and
INT-R9 before public use
(`policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:500-760`;
`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:7`).

Consequences:

- INT-R1 cannot estimate a frequentist miss rate from historical promotions.
- A prior probability of “an unknown obligation exists” would be authored rather than learned.
- A numerical confidence score for world completeness would be false precision.
- Future empirical evidence can measure challenger yield, source-detection latency, mutation
  score, review disagreement, TTL violations, and post-publication reissue frequency; it cannot
  retrospectively convert current absence of data into a calibrated coverage probability.

## 10. Pattern pass and audit-ready findings

| Pattern | Current finding | Correct research target |
| --- | --- | --- |
| `P01` contract-only capability | INT-R1 outputs are named in backlog and Atlas, but no producer/bridge exists. | Typed research sketches with explicit capability labels; no capability claim. |
| `P04` parallel status lattice | Three requested coverage labels could be mistaken for authority states. | Treat them only as evidence inputs mapped into existing N9/Atlas statuses. |
| `P05` authority dilution | A green δ chip could be read as unconditional. | Mandatory rider “relative to the declared obligation set,” remainder, TTL, and currentness. |
| `P10` structural completeness | Exact enum/partition equality can masquerade as semantic completeness. | Separate mechanical denominator totality from external obligation adequacy. |
| `P13` governance gravity | A large new coverage service could duplicate N9/N11/N12/claim owners. | Extend existing owners; create no parallel runtime from research. |
| `P14` evidence independence inflation | Same-code replay or shared source index could be called independent. | Bind independence dimensions and use an oracle outside the mutated path. |
| `P29` authorial proof | Producer-filled diligence fields could self-attest coverage. | Independent review, source-bound recomputation, challenger route, and mutation falsifier. |
| `P31` instance patching | Adding one missing class after every incident leaves the class of omission open. | Generic source-to-obligation coverage over declared bases, plus amendable vocabulary. |
| `P32` trust by form | Presence of envelope fields could be accepted without resolving hashes/owners/versions. | Resolve, content-bind, verify provenance, and fail closed on non-resolution. |
| `P33` teaching to the test | A validator may detect only the named removed obligation. | Generate variants across classes, sources, scopes, conflicts, and validator fault modes. |

### Confirmed negative findings

1. The repository proves **internal totality relative to a closed 15-class enum**, not global
   obligation completeness.
2. The enum is presently capability-gating because exact equality participates in promotion;
   it is not protected by Rule 12 merely because it is typed.
3. The P29 complete-by-construction stopping point closes schema/runtime coverage but cannot
   close an external open-world universe.
4. No empirical history currently supports a calibrated probability of missed obligations.
5. No implemented `ObligationCoverageEnvelope`, `ValidatorGovernanceRecord`, independent
   coverage validator, or complete challenger→reissue chain was found.
6. The repository already contains the correct owners and fail-closed destinations needed to
   avoid a parallel lattice or a new authority subsystem.

These findings support an `accepted_narrow_scope` answer for INT-R1: global completeness is
refuted, while bounded relative coverage remains a viable research target.
