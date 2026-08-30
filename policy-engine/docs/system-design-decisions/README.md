---
title: PolicyOS System Design Decisions
status: active
owner: team-architecture
created: 2026-05-14
---

# PolicyOS System Design Decisions

This directory captures system design decisions that are broader than a single
implementation plan but not yet accepted as formal ADRs.

Use this directory for decisions that define how PolicyOS should be shaped as a
system: authority boundaries, evidence semantics, cross-component contracts,
runtime truth, projection rules, and diagnostic substrate design.

Do not use this directory for:

- implementation checklists;
- sprint plans;
- task breakdowns;
- temporary debugging notes;
- one-off remediation patches.

Those belong in `docs/plans/`, `docs/backlog/`, or `_build/diagnostics/`.

## Relationship To ADRs

ADRs in `docs/adr/` are accepted architecture records and may be machine-indexed
by repository gates. System design decisions here are a design-review layer
before ADR acceptance.

A document in this directory may later become one or more ADRs. Until then, it
is intentionally explicit about status, open questions, and consequences.

For universal Policy Design Case operations, use
`docs/reference/policy-design-case-operator-guide.md` as the W5.E operator
lookup path. Promotion, hold, rollback, and kill-switch procedures live in
`docs/runbooks/policy-design-case-rollout-rollback.md`. Those pages link back
to this index and the append-only decision log when a reversible design
decision has not yet become an accepted ADR.

## Document Shape

Each decision document should include:

- status and date;
- problem statement;
- non-goals;
- core decision;
- design principles;
- authority boundaries;
- affected diagnostics and backlog items;
- consequences and tradeoffs;
- open questions;
- criteria for promotion to ADR.

Avoid checkbox task lists. If a document starts to describe ordered
implementation work, move that part to `docs/plans/`.

## Current Decisions

| Decision | Status | Scope |
|----------|--------|-------|
| [Honest Diagnostics Substrate](honest-diagnostics-substrate.md) | Draft umbrella, ADR core accepted | Runtime evidence authority, provenance, mode, fallback/degradation, phase barriers, scorecard/readiness/approval semantics |
| [Best-In-Class Policy Design Operating Model](policy-design-best-in-class-operating-model.md) | Draft design decision | Assurance-case-aligned policy design case, reuse-first capability realization map, Scholar academic evidence producer, concept spine, legal/data/method authority, evidence portfolios, multiverse/specification curves, argument-bearing claim compiler, effective oversight, requester-capture controls, lifecycle, ex-post learning, calibration, governance/publication boundaries |
| [Policy Design Case Decision Log](policy-design-case-decision-log.md) | Active append-only log | Reversible implementation-time ownership assignments, temporary exceptions, proof-obligation owners, Wave 35/Wave 41 disposition entries, and docs-ADR integration context used by W5.E operator guidance |
| [Universal Policy Design — System Vision And Organizing Rules](universal-policy-design-system-vision-and-organizing-rules.md) | Draft organizing constitution (post-S14) | B-on-A vision, narrow-waist anatomy and dependency rule, the twelve organizing invariants (incl. free-growth: capability follows the corpus, discovered by search, never enumerated — no hardcode fallbacks), the ports/adapters/registry/conformance discipline for subordinating engines, architectural strengths and the six necessary tradeoffs (with health metrics and open questions), capability reality bar, honest current state, and forward direction |
| [PolicyOS Atlas Surface Constitution And Frontend Vision](policyos-atlas-surface-constitution-and-frontend-vision.md) | Draft derived surface constitution | Frontend, design-system, public/trust/docs, and product-flow laws derived from the Universal Policy Design constitution; surface capability definition of done; status grammar split between authority, interaction, and capability-reality states; Atlas v15 admission posture; proving-ground board as first honest flagship surface |
| [PolicyOS Identity And The Custody Boundary](policyos-identity-and-custody-boundary.md) | Ratified design decision (2026-07-20) | System identity as epistemic custodian of policy justification; the signature rule; the four-way own/integrate/observe/out_of_scope test and its rulings on the contested zones; binding anti-roles; the cheap-extension criterion; three horizons |
| [Stage-0 Custody Kernel — Ratification Record](stage0-custody-kernel-ratification.md) | Ratified design decision (2026-08-02) | The sixteen custody invariants S0-K01–S0-K16 — identity, boundary, authority, temporal, custody, and benchmark; the authority-band/candidate-band lens that keeps strictness from eating capability; three amendments (custody-subject naming, oracle independence scoped to verification claims, fail-closed scoped to protected actions); the accepted prices and the commissioning of S0-GAP-02 |
| [INT Wave Claim Semantics — Ratification Record](int-wave-claim-semantics-ratification.md) | Ratified design decision (2026-08-04) | The eight claim-semantics invariants INT-K01–INT-K08 — what a **number** may mean: relative obligation completeness, the declared-set rider every δ must carry, constructed independence for `bounded_complete`, when risk composes across scopes, and INT-K06's third outcome — a binding falsifiable claim about **procedure** carrying no probability at all |
| [Public Verification And Disclosure — Ratification Record](int-r7-r8-public-verification-and-disclosure-ratification.md) | Ratified design decision (2026-08-05) | The nine invariants PV-K01–PV-K09 — what a public **proof** and a public **projection** may mean: verification as a separately reportable vector rather than a signature bit, historical authenticity never erased by a present evidentiary failure, the proof/content seam, use-relative conservative parity, three categorical omission blockers, exact-or-proved-conservative reconstruction, prefix discipline as the accepted no-number claim, the premise-relative refusal of a canonical disclosure number, and proof metadata as part of the disclosure channel |
| [Decision Evidence And Repository Standing — Ratification Record](wave4-decision-evidence-ratification.md) | Ratified design decision (2026-08-17) | The six statements W4-K01–W4-K06 — what the deciding **machinery** may turn on, where the three prior acts govern outputs: a walk settles the number but not who may cite it (holder-relative attribution, and an `institutionally_supplied` census cannot settle a zero), the five predicate-provenance labels are fixed with refinements as sub-annotations, a condition added to preserve a positive is itself a gate predicate (no fixed point until it is constructed at the level of the property it names), a proxy gate must name its divergent case, three separate standing axes each bound to a registered vocabulary, and `absent/unallocated` as the weakest capability label; withdraws OPS-R14's `F-14A` and records the wave's own process defects rather than absorbing them |
| [Evidence Substitution Boundaries — Ratification Record](wave5-evidence-substitution-ratification.md) | Ratified design decision (2026-08-30) | The six statements W5-K01–W5-K06 — **what one kind of evidence may not stand in for**, where the four prior acts govern a kind of output or gate: rows in a data stream cannot close a non-data gap (relation, estimand, mandate, capacity, licence, authority, assurance — eight types, 28 preserved pairwise distinctions), surface/enforcement/instrument conformance cannot be projected as human comprehension, post-deployment observation cannot become a causal claim before admission and `diagnosis_unresolved` freezes the update, a protective response and an unresolved cause may share one record but the response is never the evidence, a certificate through `t0` does not determine `t1` when a decisive dependency can change (an information limit, not a claim that authority differs), and translation or locale parity cannot establish source-language authority. Twelve binding negatives; the constitution is not amended and the outcome-vocabulary trigger stays armed |
| [Withheld Propositions Register](withheld-propositions-register.md) | Active standing register — append-only (opened 2026-08-30) | Propositions that are researched, evidenced and **deliberately not bound**, because binding them would leave the authority band. Four typed withholding reasons say what would have to change: `constrains_computation` waits for evidence, `constrains_action` for a scope decision, and `presupposes_absent_capability` / `presupposes_absent_institution` are **build targets today** under the identity decision §9 item 5. Seeded with wave 5's thirteen — the seven governed response-action families, the transition charter, the asymmetric restart rule, the eight-condition posterior-update conjunction, the SMDV-1 precedence, the no-universal-numbers discipline, the English-pivot split, the RTL evidence pack. Fed by contract: pipeline §3.6 names the withheld set a consolidation deliverable and §3.7 requires act §9 to cite `WP-` IDs |
| [Custody Time Model (CTM)](policy-design-custody-time-model.md) | Accepted target spec (2026-08-02) | The fourth layer of the causal OS (data · grounding · search · **time**): nine primitive temporal roles as a sparse semantic profile, relations instead of clocks, explicit query coordinates instead of an overloaded `as_of`, family-native persistence with adapters, the advisory late-event reaction ladder; refutes the universal persisted event envelope and prescribes the `TimeSourceEnvelopeAudit` narrowing |
