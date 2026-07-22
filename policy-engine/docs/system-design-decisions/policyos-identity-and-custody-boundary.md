---
title: PolicyOS Identity And The Custody Boundary
status: ratified design decision — system identity and scope boundary
owner: team-architecture
created: 2026-07-20
last_reviewed: 2026-07-20
decision_status: accepted — ratified by the human principal (owner decision, 2026-07-20); this document is the human-principal acceptance record required by constitution §12 for the §1 amendment it introduces
supersedes: nothing (sharpens the constitution's §1 Vision; the amendment is recorded there and points here)
informs:
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/policy-design-causal-operating-system-north-star.md
  - docs/research/policy-operations-and-real-world-runtime-backlog.md
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
  - docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
related:
  - docs/research/deep-research-value-distillation.md
  - docs/reference/policy-design-case-failure-patterns.md
authoritative_for: [system_identity, scope_adjudication, own_integrate_observe_boundary_rulings]
may_not_use_for: [capability_claim, task_execution_contract, jurisdiction_specific_legal_conclusion]
---

# PolicyOS Identity And The Custody Boundary

## 1. The decision in one sentence

**PolicyOS is the epistemic custodian of policy justification across the whole life of a
policy: it owns everything it signs, for exactly as long as the signature publicly stands;
it consumes everything others sign as typed evidence; and it makes no claims it cannot
custody.**

## 2. Why this decision exists (trigger)

Scoping the second research wave (`docs/research/policy-operations-and-real-world-runtime-backlog.md`,
67 tasks) exposed an architectural presumption that had never been decided: whether
PolicyOS should become the *operational backbone* of policy administration (owner of case
continuity, fleets, portfolios, administrative interfaces) or remain an *authority core*
that deliberately delegates operations. Left undecided, that presumption would have been
smuggled in through dozens of research tasks that assume ownership. Three candidate
identities were weighed:

- **A. Policy design studio** (narrow): the system ends at a publishable design.
- **B. Custodial core** (this decision): design authority + lifetime custody of
  justification + a safe post-deployment learning loop.
- **C. Policy operations runtime** (wide): owner of administrative continuity —
  clocks, notices, redress workflows, fleets, service delivery.

The owner ratified **B**, with the explicit qualifier that cheap extensions which are
*projections of the core* remain in scope (see §7), and that C remains a decades-scale
north-star reachable by institutional *adoption* of the custodial core — never by building
an ERP (see §8).

## 3. The argument: the honesty constitution already decides the boundary

The whole constitution rests on one promise: **every published claim is provably
admissible.** That promise has a time dimension the system has already conceded by
building epochs, staleness, the perturbation cascade, and `EvidenceValidityEvent`
semantics: a claim honest at t0 silently becomes false at t1 when law, data, calibration,
or the world changes. Two conclusions follow, one against each extreme:

- **Too narrow violates the constitution.** A "design studio" that emits a grounded
  design and walks away leaves its own published signatures to rot — dishonest by its own
  standard. And the system's signature move — *refusal with a path* — dies if a case
  cannot wait months and wake correctly: refusal-with-a-path without durable suspension
  is refusal-with-a-dead-end. Custody is not an extension of honesty; it is its
  completion.
- **Too wide owns other people's signatures.** The system never signs "the letter was
  delivered," "the payment cleared," "the inspection was fair." Those are other
  institutions' claims. Owning their execution means owning signatures the system cannot
  honestly make — the ERP gravity well (failure pattern P13 at institutional scale).

## 4. The identity: what the system must be when current work completes

Three roles, and explicit anti-roles.

1. **Design authority** (GY Phase 5; near-complete). Take a policy problem and produce
   either a grounded design — typed evidence, set-valued value, δ-accounted promotion
   risk, and a publishable, citizen-verifiable record — or an honest, *costed* refusal
   with an executable path to close the gap.
2. **Justification custodian** (partially built: N12 epochs, the M36 perturbation
   cascade, Decision-Validity; this is the *epistemic* half of "operations"). The "why"
   of every signed decision stays honest over time: inputs drift, signatures go stale,
   perturbations (appeals, incidents, retractions, amendments) cascade into
   revalidate / reissue / supersede / withdraw — with full historical provability.
3. **Learning loop** (GY Phase 6; greenfield). Deployed outcomes grow the causal world
   model safely (performativity-aware, self-confirmation-proof), under the same
   candidate→authority discipline as everything else.

**Anti-roles (binding):** PolicyOS is not an administrator, not an executor, not a
case-management system, not a court, not a notification channel, not a payment system,
not a CRM. These are commodity or sovereign functions owned by other systems and
institutions.

**Differential value.** Case management exists; document management exists; budget
systems exist. **A lifetime custodian of policy justification exists nowhere.** All of
the system's differential value — and its honest public promise — concentrates there.
This is not digitization for its own sake; it is the one function no other system
provides.

## 5. The signature rule and the four-way boundary test

The operational form of the identity. For any candidate function, ask in order:

1. **Does its absence make one of OUR published claims silently false?** → **OWN.**
   (The function is part of custody; build and operate it.)
2. **Does its output change the validity of our claims?** → **INTEGRATE.**
   (Consume it as typed evidence through a fail-closed contract: the evidence interface,
   its provenance, and its absence-behavior are ours; the function is not.)
3. **Does it change only who answers for our claims?** → **OBSERVE.**
   (Track it — e.g., institutional successions — to freeze/reassign authority; never
   manage it.)
4. **Otherwise** → **OUT_OF_SCOPE.**
   (Name the external owner and the contract that would connect them, and stop.)

Corollaries:

- For every INTEGRATE/OBSERVE item PolicyOS still **owns the contract**: the typed
  evidence interface, its versioning, and the fail-closed behavior when the partner is
  absent, late, or contradictory. Owning the contract is not owning the function.
- If an institution lacks the integration partner (e.g., no case-management system to
  hand off to), building a minimal shim is a **new owner decision**, never an automatic
  scope expansion under this ruling.

## 6. Boundary rulings on the contested zones

Ratified applications of the test (the adjudication baseline for Wave-2 reshaping and
future plan edits):

| Zone | Ruling | Rationale |
| --- | --- | --- |
| Durable case suspension/resume, WorldRelease, minimal recompute, event-time semantics | **OWN — core, not "operations"** | Without them custody and refusal-with-a-path do not exist. Completion of honesty. |
| Weekly legal release, jurisdiction packs | **OWN** | Lex is the system's sensory organ; living law = living signatures. High value, cheap on existing machinery. |
| `PolicyMatter` identity above a single case | **OWN, now** | Cheap now, brutally expensive to retrofit. |
| KPI control contract + diagnosis semantics | **OWN contract / INTEGRATE data collection** | Reuses DDM/`MonitoredMetric`; the decision-linkage is ours, the sensors are not. |
| Appeals, incidents | **INTEGRATE** | Adjudication outcomes are cascade events (M36 gives ingestion nearly free). The redress workflow itself is another institution's. |
| Administrative clocks, notices, payments, procurement, physical delivery | **INTEGRATE / OBSERVE** | Consume proof-of-service / execution status as implementation evidence. Never execute. |
| Public correction of OUR published records | **OWN** | Our signatures; durable-notice fan-out for them is custody. |
| Fleet / portfolio at scale (10 000 cases) | **OWN later** | Custody-at-scale is legitimate — but there is one real case today. Design compatibly (identity now), build after the first pilot. |
| Individual-decision firewall | **OWN the firewall** | The prohibition (policy-level output never decides an individual case) is our claim and our gate; the individual decision is never ours. |
| Omnichannel service journeys, enforcement discretion, whistleblower channels, foresight programs | **OUT_OF_SCOPE / defer** | Other institutions' signatures and sovereign functions. Track as deferred research until a pilot produces institutional facts. |

## 7. The cheap-extension criterion

The owner's qualifier — "do not be too narrow when an extension seriously raises
usability and value at low cost" — gets a precise form: **an extension is worth taking
exactly when it is a projection of already-built core machinery, and not worth taking
when it requires owning a new subsystem.** Examples: the perturbation cascade makes
appeal/incident *ingestion* nearly free; the epoch layer makes staleness surfaces nearly
free; DDM makes the KPI contract nearly free — take them. Omnichannel intake or payment
reconciliation require new sovereign machinery — decline them, integrate instead.

## 8. Three horizons

- **H1 (current plans):** design authority — first governed promotion, first publishable,
  citizen-verifiable record.
- **H2 (the completion this decision defines):** the custodial core — design + lifetime
  justification custody + safe learning loop.
- **H3 (north star, decades):** a policy operating system for institutions — fleets,
  portfolios, interagency reliance — reached by institutional **adoption** of the
  custodial core, never by building our ERP. (Consistent with the north-star doc: the
  primary product is the growing causal world model; policies are programs against it.)

## 9. Binding consequences

1. **For the two active plans (GY, Atlas):** no new task may take ownership of a function
   outside the boundary; the alternative is always a typed integrate-contract. Existing
   in-flight tasks (N11, DS4) are untouched.
2. **For the Wave-2 research backlog:** reshape under this decision — an active core
   (all `INT-R*`; the `OPS-R*` spine, with known-pattern tasks recast as
   "adapt-pattern + authority-delta"; `PAO-R0`/`PAO-R1`; the capstone re-cut to the
   custody cycle; the cheap core-projections) and a `deferred_until_pilot` registry for
   the rest — deferred zones are not deleted; they await institutional facts only a real
   pilot can produce. The backlog's open meta-question ("should PolicyOS own operational
   continuity?") is **answered by this decision**: it owns *epistemic* continuity
   (custody), integrates *administrative* continuity.
3. **For every future backlog/task:** the four-way test of §5 (`own / integrate /
   observe / out_of_scope`) is a mandatory field, adjudicated against this document.
4. **For the constitution:** §1 Vision gains an additive amendment block naming this
   identity and pointing here (recorded per §12; this document is the acceptance record).

## 10. Impact note (constitution §12 requirements)

- **Status lattice:** no new statuses. The identity constrains *which surfaces exist*,
  not how statuses compose; the one-lattice law (Atlas DS4) is unchanged.
- **Authority boundaries:** unchanged in shape; this decision *narrows* where authority
  slots may be created (no slots for out-of-boundary functions) and mandates
  integrate-contracts with fail-closed absence behavior in their place.
- **Replay behavior:** unchanged. Closed cases replay under the rules that closed them;
  this decision is forward-looking (rule-version reference: this document's `created`
  date; cases closed before 2026-07-20 are interpreted under the prior, silent scope).
- **Affected plans:** GY and Atlas gain a scope-adjudication reference, no task changes
  beyond those already landed (Rev 18 / Rev 3.3). The Wave-2 backlog is marked pending
  reshaping.

## 11. Revisit conditions

- **After the first governed real-world pilot:** re-adjudicate the `deferred_until_pilot`
  zones with the institutional facts the pilot produces (which integration partners
  actually exist, which shims institutions actually need).
- **If H3 adoption pressure arrives** (an institution asks PolicyOS to own an
  administrative function): the request routes through §5's test and, if it fails OWN,
  through the shim rule of §5's corollary — as a new owner decision, recorded as an
  amendment to this document.
- **If custody proves economically unsustainable at fleet scale:** revisit the OWN-later
  rulings of §6 before weakening any custody guarantee; degrading honesty is not an
  admissible cost reduction.
