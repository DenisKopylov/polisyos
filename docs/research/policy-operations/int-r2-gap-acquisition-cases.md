---
title: INT-R2 — Gap Acquisition Cases For Non-Data Objects
status: stage_1_research_delivered
kind: deep-research
research_task: INT-R2
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r2-research
repository_base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
authoritative_for:
  - research-level candidate semantics for classifying and acquiring eight non-data gap objects
  - research-level authority-ceiling, re-entry and deeper-terminal tests
  - later consolidation and ratification input for the missing knowledge/grounding acquisition plane
may_not_use_for:
  - capability claim
  - canonical owner appointment
  - institutional signer appointment
  - production admission
  - authority grant
  - public-signature release
  - final runtime or wire contract
research_only: true
---

# INT-R2 — Gap Acquisition Cases For Non-Data Objects

## 1. Task And Project Fit

### 1.1 Exact question and result boundary

INT-R2 asks how PolicyOS should model acquisition of eight things that are not interchangeable with
additional data rows:

1. a grounding relation;
2. an estimand binding;
3. owner writability;
4. a legal mandate;
5. a normative authorization;
6. implementation-capacity evidence;
7. a competent human decision; and
8. an independent audit.

The result is a research-level candidate `GapAcquisitionCase` discriminated union. Each branch answers
six questions independently: who may produce the object; what closes its acquisition requirement;
what admission proof is required; what checkable authority ceiling follows; how the original gate is
re-entered; and what a `deeper_terminal` means for that branch.

The task is research-first because each branch changes what a future gate would be permitted to turn
on. A convenient schema written before the producer, sufficiency rule, authority boundary and
institutional dependency are understood would convert an unresolved premise into a positive-eligible
predicate. That is the P37 failure this pipeline forbids. Stage 1 therefore specifies candidate
semantics and falsifiers; it does not create the canonical runtime owner or make any acquisition
operational.

### 1.2 False production claims prevented

The package is designed to prevent five specific false claims:

- **row-count closure:** many relevant observations are treated as if they establish a causal
  relation, choose an estimand or create a mandate;
- **document-by-presence closure:** a signed letter, credential, approval, checklist or audit report is
  accepted because it exists or parses, without resolving issuer competence, scope, work performed and
  current validity;
- **authority-ceiling theatre:** a record says `limited authority` but no consumer can test the action,
  object, population, jurisdiction, purpose, time or maximum claim strength that the limitation
  permits;
- **terminal-as-progress:** a more specific negative finding is rendered as “almost approved” merely
  because more work was performed;
- **borrowed institution:** an external practice is copied into a contract that silently assumes an
  appointed adjudicator, ethics body, register owner, competent decision-maker or independent provider
  that PolicyOS does not have.

The adversarial invariant is exact:

```text
For case_type in {grounding_relation, estimand_binding, legal_mandate}:
    add any number of rows to the current data stream
    while leaving the required non-data acquisition object absent
    => the case remains unclosed.
```

This does not say that evidence is irrelevant. It says that a row is admitted only for the predicate
it can change. A new experiment, new measurement regime or owner-produced decision artifact may be
relevant to relation acquisition; an enabling statute may depend on factual predicates. But the system
must name the change in evidence regime or authority object. It may not treat `n increased` as a
universal closure operator.

### 1.3 Four-way identity-boundary verdict

The ratified identity says PolicyOS owns the integrity of claims it signs, consumes other
institutions’ signatures as typed evidence, and does not become an administrator, court, ethics body,
register, auditor or service-delivery organisation
(`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:55-112`). INT-R2
therefore has a composed boundary, not one blanket owner verdict:

| Plane | Verdict | INT-R2 consequence |
| --- | --- | --- |
| Typed demand, classification, admission interface, ceiling enforcement, re-entry and claim reaction | **OWN** | Without these, PolicyOS can silently upgrade an unclosed blocker and make its own signed claim false. |
| Production of mandates, consent/ethics decisions, canonical register grants, professional decisions, assurance and delivery-capacity assessments | **INTEGRATE** | PolicyOS owns the fail-closed evidence contract and verification of the received artifact; the external institution owns the act. |
| Issuer succession, revocation, professional standing, assurance relationships and changes in the external institutional environment | **OBSERVE** | These events can stale or reopen PolicyOS claims, but PolicyOS does not administer the institutions. |
| Performing legislation, ethical adjudication, register adjudication, professional licensing, independent audit or policy delivery | **OUT_OF_SCOPE** | A missing partner remains a typed external-institution blocker. Scarcity does not transfer the function to PolicyOS. |

The commission describes this package as turning a legitimate route to a missing plane into an owner.
Stage-1 authority law narrows that phrase: this package makes the **candidate ownership boundary and
integration contract specifiable**. It cannot appoint the canonical owner. Owner appointment, adoption
and implementation remain later consolidation/ratification decisions.

### 1.4 Project fit and standing

The work is the stand-alone “+1” in Wave 8. It consumes the existing N13a/N13b residual evidence and
is a possible input to GY Phase 6 / O1/O3, but it is not part of the declared `INT-R4` ‖ `OPS-R5` pair.
It must not depend on that pair’s unresolved future result.

Standing is reported on W4-K05’s three independent axes:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

- `accepted_narrow_scope`: the eight-way candidate semantics and non-closure invariant are suitable
  for audit and consolidation, subject to the limitations recorded below;
- `absent/unallocated`: no admitted end-to-end prerequisite chain and no appointed canonical owner
  exists for the generic union or the external institutional producers;
- `NO_GO`: the package does not permit a first public signature, governed closure or production use.

These values are not inferable from one another. A useful research result can coexist with an absent
capability and a closed gate.

## 2. Current Repo Baseline

A detailed coordinate and measurement ledger is committed at
`docs/research/policy-operations/int-r2/repo-baseline-and-source-ledger.md`. The headline result is:

> **The repository has a strong, content-bound data-acquisition path and several purpose-scoped
> authority fragments, but it has no generic `GapAcquisitionCase` owner, no residual-shape classifier,
> no eight-type producer/admission chain and no complete authority-ceiling evaluator.**

### 2.1 Mandatory inspection set

The pinned baseline study inspected the following classes of source at
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f`:

- repository instructions and contributor boundaries: `AGENTS.md` and
  `policy-engine/CONTRIBUTING.md`;
- the identity ruling and the architecture frame:
  `policyos-identity-and-custody-boundary.md`,
  `universal-policy-design-system-vision-and-organizing-rules.md`,
  `universal-policy-design-target-architecture-and-gap.md`,
  `policy-design-best-in-class-operating-model.md`, `honest-diagnostics-substrate.md` and
  `policy-design-causal-operating-system-north-star.md`;
- the failure-pattern register, including P01, P04, P05, P10, P13, P15, P21, P22, P26–P38;
- the active GY and Atlas plans and `deep-research-value-distillation.md`;
- the N13a census, N13b acquisition planner/authority/passport/overlay/re-entry owners, CG3/CG5
  grounding hooks, typed refusal service and human-decision seed.

The architecture sources converge on four constraints that control this result:

1. search and generators produce candidates; only the A-side authority gate admits them;
2. external power enters through the narrow waist with purpose, provenance, version, time and
   authority boundaries;
3. projections and reports may render authority but cannot mint it;
4. a research contract remains `absent/unallocated` until a producer→artifact→bridge→consumer→
   verification→surface chain exists.

### 2.2 Existing refusal vocabularies

The repository already refuses in several useful but non-equivalent ways:

| Vocabulary/owner | Existing meaning | Path-forward status |
| --- | --- | --- |
| PDC waist (`src/polisyos/pdc/_impl/gy_waist.py:218-255`) | `single_obligation_fail`, `joint_obligation_inconsistency`, `proof_timeout`, `scope_insufficient`, `unknown` and per-obligation outcomes. | Identifies gate posture, not the missing acquisition object; generally bare for INT-R2. |
| Authority-value service (`runtime/http/services/authority_values.py:1-150`) | Discriminated `refused | supplied` values with `no_runtime_composition_rule`, `no_runtime_estimator`, `analysis_not_runtime_resident`, `no_runtime_producer`, `owned_by_another_surface`. | `owned_by_another_surface` names a route; the remaining codes honestly explain absence but do not necessarily name a closing producer or proof. |
| Acquisition planner (`runtime/quality/acquisition_planner.py:1-360`) | Gap type, eligible strategies, authority level, mandatory-gate state and planner disposition. | Carries a path to an acquisition action but explicitly does not satisfy the domain slot. |
| N13b re-entry (`tools/quality/validation/layer3_gy_n13b_reentry.py:1-210`) | `gap_closed_by_acquisition`, `deeper_terminal_primary_carrier_characterization_failed`, `deeper_terminal_catalog_binding_absent`. | Full path for a data requirement; terminal semantics are tied to carrier/catalog evidence. |
| CG3/CG5 grounding (`runtime/quality/grounding_admission.py:1-360`; `grounding_active_controller.py:1-300`) | Typed grounding blockers, acquisition need and bounded next actions. | Routes work back through owner gates. CG5 explicitly cannot close obligations or mark a case resolved. |

This baseline supports a critical distinction: **a typed refusal is not automatically a refusal with a
complete acquisition path**. It may say what is missing without establishing who may produce it, what
proof suffices or which authority would result.

### 2.3 The N13/DS15 data-acquisition exemplar

The existing data path is the one worked example INT-R2 must generalise without copying its storage
shape:

1. a demanding stage emits a typed requirement gap;
2. `acquisition_planner.py` selects only eligible strategies and records why other strategies are
   ineligible;
3. source and rights owners are re-resolved; the acquisition registry cannot self-authorise source,
   licence, L5 or transport authority
   (`data_forge/domains/catalog/knowledge/acquisition_authority.py:1-380`);
4. raw response, journal and CAS provenance are resolved;
5. a content-bound acquisition passport admits, degrades or quarantines candidate observations;
6. admitted observations enter a separate epoch overlay while epoch zero remains immutable
   (`data_forge/domains/catalog/knowledge/overlay.py:1-90,260-620`);
7. the demanding stage re-enters and recomputes its before/after availability;
8. only actual owner-visible dataset, binding or observation growth closes the requirement; otherwise
   the route produces a more specific negative terminal.

DS15 may project these data-path states. It does not create a non-data producer or decide that a
`binding_gap` is data-shaped.

The reusable discipline is:

```text
typed demand
→ eligible producer/action
→ content-bound proof
→ purpose-scoped admission
→ bounded authority
→ owner-gated re-entry
→ replayable closure or stronger refusal
```

The non-reusable assumptions are:

```text
acquired object = observation row
admission = data passport
persistence = overlay epoch
closure = dataset/binding/observation count increased
```

A causal relation, estimand, mandate, decision or audit cannot truthfully close by being forced into
those four shapes.

### 2.4 Data-gap gravity already present at the grounding seam

The acquisition planner has legal, method, scholar and participation gap families, but the current
value-input and grounding-coverage bridges still carry `data_requirement` or `routing_only` semantics.
CG3 can emit `AcquisitionNeed`; CG5 can select `elicit_human` or `acquire_data`; neither defines the
admitted object or grants the external producer standing.

This is not merely missing metadata. Three data-path invariants break for non-data acquisition:

- **wrong closure predicate:** availability-count growth says nothing about whether a relation was
  adjudicated, an estimand was defined or a mandate was validly issued;
- **wrong producer model:** a connector/source owner is not a legislature, ethics body, register owner,
  competent decision-maker or independent assurer;
- **wrong authority effect:** an admitted observation can support an evidentiary claim within its data
  ceiling; it cannot authorise an action or create the meaning of the target quantity.

Therefore a future implementation may reuse planner discipline, CAS identity, owner re-resolution,
quarantine, epoching and re-entry patterns, but not the observation-passport closure rule.

### 2.5 Authority representation today

PolicyOS already carries several ingredients:

- `authoritative_for` / `may_not_use_for` on research, runtime and projection artifacts;
- `AuthorityLevel` (`research | governed | production`) and mandatory-gate posture in the acquisition
  planner;
- content-bound acquisition passports and explicit quarantine/non-admission;
- `not_established` as the fail-closed P37 predicate-provenance label;
- `absent/unallocated` as the capability-reality label when no admitted chain or owner exists;
- scope, purpose, time, identity and provenance fields in specialised legal, data, grounding and human
  records.

What is absent is one owner-computed predicate equivalent to:

```text
requested_use ∈ admitted_artifact.authority_ceiling
```

for all eight INT-R2 variants, where the ceiling simultaneously binds action/claim, subject/object,
population, jurisdiction, purpose/audience, effective and review windows, assumptions/evidence class,
maximum claim strength or commitment stage, permitted operation and prohibited downstream uses.

Thus the baseline sentence required by the commission is:

> **Nothing in the pinned repository can express and enforce a complete generic authority ceiling for
> all eight case types today. Existing fragments are reusable, but the aggregate evaluator and its
> registered cross-type vocabulary are `absent/unallocated`.**

### 2.6 CG5 and the missing acquisition plane

CG5 is intentionally a consumer/router. Its module contract says it reads CG1–CG4 certificates,
chooses a bounded next action and routes results back through gates; it never closes obligations,
injects evidence, writes gate dispositions or marks resolution. This is a correct separation of
control from authority.

`GY-engine-subordination.md:2410-2495` then records the honest residual: N13b converted none of the 15
binding gaps into world growth, while three capstone `not_a_data_gap` routes were sent to a future
knowledge/grounding acquisition plane — “CG5-class relation/lever acquisition + estimand evidence” —
outside N13b’s scope.

INT-R2 therefore does not replace CG5. It specifies the candidate **case contract that a future
producer plane would have to satisfy before CG5’s routed work could re-enter an owner gate**.

### 2.7 Census and the fourteen unclassified residuals

The committed N13a census supplies a complete 15-row ranked `growth_backlog`; every row says
`gap_kind: binding_gap`. It also contains three capstone route-evidence rows classified
`not_a_data_gap`.

The later measurement supplied in the commission says one of the 15 was independently established as
data-shaped, 14 remained `shape: not_established`, and zero were structurally classified. Holder
standing matters:

- the pinned 15-row and three-route collections were read from their owner artifact and are
  `recomputed` for this package;
- the later `1 data-shaped / 14 not_established` partition is `institutionally_supplied` because the
  later executing slice is not present at the pinned tree;
- the supplied zero structural classifications is not a settled zero for this holder under W4-K01/P35.
  The safe statement is `structural classification not established here`.

Most importantly, `binding_gap` is not a discriminator. It says that some binding is absent. It does
not say whether the missing object is a row, relation, estimand, write right, mandate, authorization,
capacity proof, decision or audit.

The fourteen must therefore remain `not_established` until each residual has evidence for:

1. the exact demanding gate and load-bearing predicate;
2. the minimal missing object whose presence could change that predicate;
3. a same-stream row-invariance test;
4. the competent producer/owner and proof of its standing;
5. the target/estimand and relation requirements, if any;
6. applicable write, legal, normative, capacity, decision and assurance requirements;
7. ruled-out neighbouring variants, with evidence; and
8. `split_required` when more than one acquisition object is independently necessary.

Unknown shape must never default to `data_requirement`.

The three capstones can be narrowed now:

| Route | Current classification |
| --- | --- |
| `education` — `method_estimand_binding_mismatch` | `estimand_binding` candidate; additional identification or data gaps may coexist but do not replace the target-binding case. |
| `first_vertical` — `grounding_relation_or_owner_lever:gy_n4.emergency_tax_relief` | Unresolved disjunction: `grounding_relation` if the causal/grounding edge is absent; `owner_writability` if the relation exists but no canonical owner may register the lever; ordered two-case sequence if both are absent. |
| `unseen` — `grounding_relation_or_owner_lever:candidate_fallback_1950390310ca54cb` | Same disjunction and split rule. |

The two disjunctive routes are not justification for a hybrid ninth union variant. They demonstrate
why classification and case construction must be separate stages.

### 2.8 Reuse-first integration path and current labels

The smallest visible later integration path is:

1. extend the canonical acquisition planner’s demand/routing boundary rather than creating a second
   planner;
2. add a pre-union residual-shape assessment owned by the future non-data acquisition plane;
3. reuse CAS/provenance, resolve-bind-verify, quarantine, epoch and re-entry disciplines;
4. extend existing legal, grounding, human-decision and audit owners for their domain artifacts rather
   than duplicating them;
5. make each demanding gate re-resolve the admitted artifact and enforce its ceiling;
6. let Atlas render the existing one-lattice outcome; do not create a parallel status lattice.

Current capability labels are:

| Slice | Label | Missing prerequisite |
| --- | --- | --- |
| Generic `GapAcquisitionCase` union | `absent/unallocated` | No admitted canonical contract, appointed owner, producer or consumer chain. |
| Residual-shape classifier | `absent/unallocated` | No owner-computed discriminator over the missing acquisition object. |
| Generic authority-ceiling evaluator | `absent/unallocated` | No complete registered vocabulary or consumer-side evaluator across the eight variants. |
| Institutional producers/signers | `absent/unallocated` | The necessary accountable external actors and commitments are not appointed. |
| Multi-type re-entry bridges | `absent/unallocated` | No admitted non-data artifact is wired back to every demanding canonical gate. |
| Adversarial semantic fixtures | `semantic_test_missing` | No executable proof yet preserves relation/estimand/mandate refusal under arbitrary row inflation. |

Repo blockers split cleanly:

- **research blockers:** no universal scientific threshold for causal relation acquisition; no
  model-free proof that an unclassified residual is structural; no generic issuer for social licence;
  weak calibration of expert causal structure and broad delivery-confidence scores;
- **engineering blockers:** absent union/classifier/ceiling contract, persistence, bridges, consumers,
  validators and surfaces;
- **institutional blockers:** no appointed competent grantors, normative bodies, canonical write
  owners, decision-makers or independent assurance providers.

None is repaired by adding rows to the data overlay.

## 3. External Research Baseline

## 4. Result

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation
