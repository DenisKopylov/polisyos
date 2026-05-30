---
title: Policy Design Case Structural ADR Registry
status: active
owner: team-policyos-runtime
created: 2026-05-22
source_research_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
source_synthesis: ../backlog/universal-policy-design-case-research-results-consolidation.md
raw_research_ledger: ../research/universal-policy-design/deep-research-reports-105-146-combined.md
implementation_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
failure_patterns: policy-design-case-failure-patterns.md
source_ownership: policy-design-case-source-ownership.md
evidence_paths: policy-design-case-evidence-paths.md
operator_guide: policy-design-case-operator-guide.md
rollout_runbook: ../runbooks/policy-design-case-rollout-rollback.md
adr_index: ../adr/index.md
---

# Policy Design Case Structural ADR Registry

This page is the W0.H registry for the universal Policy Design Case program.
It maps every structural research decision from C0 through C41 to a decision
source before later waves turn those decisions into tables, schemas, gates, or
runtime behavior.

Coverage is explicit from `C0` through `C41`. The implementation plan splits
the external legitimacy item into C39a and C39b, so this table records those
two rows rather than a single collapsed C39 row.

The registry is intentionally narrower than a design spec. It answers one
load-bearing question:

```text
May this structural implementation proceed, and what decision source does it cite?
```

If the answer is "no accepted decision source", the implementation gate is
`blocks_structural_implementation`. A later wave may still prepare fixtures,
exploration notes, or advisory experiments, but it may not merge a structural
commitment that lacks an accepted ADR, a fast-track ADR, a named future ADR, or
an explicit `no_adr_required` rationale.

## Registry Classes

| Registry class | Meaning | Merge posture |
| --- | --- | --- |
| existing_adr | An accepted pre-W0 ADR already ratifies the structural boundary. | Implementation may proceed if it stays inside the cited ADR authority and tuned parameters remain governed config. |
| fast_track_adr | One of the six W0 fast-track ADRs, ADR-0166 through ADR-0171, ratifies the decision. | Gated implementation may proceed after the cited ADR is accepted and its negative laundering tests are preserved. |
| new_adr_required | The decision is structural and no accepted ADR currently ratifies the boundary. | Structural implementation is blocked until the named ADR is written and accepted. |
| no_adr_required | The item is implementation-local, tuned-config only, deployment-owned, or still empirical/research-blocked. | No new structural ADR is required now, but the row names what may not be hardened as architecture. |

For `no_adr_required`, the rationale label must be one of:
`implementation_local`, `tuned_config_only`, `deployment_owned`, or
`research_blocked`.

## C0-C41 Decision Source Registry

| Ref | Research decision | Registry class | Decision source | Implementation gate | Rationale label | E tasks | Pattern pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | Capability baseline and canonical paths | existing_adr | [ADR-0157](../adr/0157-policy-intent-capability-ledger-authority-profile.md), [ADR-0146](../adr/0146-product-root-decision.md), W0.G source ownership | Capability ratchet work may proceed only with canonical repo paths and source-chain links. | - | E0,E1,E23 | P01,P06,P13 |
| C1 | Status algebra and soft-gate semantics | existing_adr | [ADR-0150](../adr/0150-scorecard-readiness-approval-projection-boundaries.md), [ADR-0156](../adr/0156-policy-design-case-runtime-quality-assurance-profile.md) | Status envelope implementation may proceed; new cross-system terminal states require composition tests before use. | - | E2,E19 | P04,P09,P10 |
| C2 | Admissibility and authority-level calculus | existing_adr | [ADR-0150](../adr/0150-scorecard-readiness-approval-projection-boundaries.md), [ADR-0157](../adr/0157-policy-intent-capability-ledger-authority-profile.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md) | Admissibility readers may compose authority levels, but projection or LLM content cannot satisfy evidence slots. | - | E2,E3,E9-E13 | P05,P10,P15 |
| C3 | Unified closeout substrate semantics | existing_adr | [ADR-0148](../adr/0148-serious-run-state-machine-and-phase-barriers.md), [ADR-0150](../adr/0150-scorecard-readiness-approval-projection-boundaries.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md), [ADR-0165](../adr/0165-formal-policy-case-substrate-invariant-specs.md) | Closeout reader work may proceed; dashboard, API, export, or audit views may display but not mint closeout authority. | - | E3 | P01,P02,P05,P10 |
| C4 | Universal facet grammar | new_adr_required | ADR-TBD-universal-facet-grammar-and-obligation-owner | blocks_structural_implementation for facet vocabulary, ownership, and cross-producer obligation semantics beyond exploratory fixtures. | - | E10,E17 | P01,P05,P13,P15 |
| C5 | Obligation rule lifecycle and governance | new_adr_required | ADR-TBD-obligation-rule-lifecycle-and-governed-rulebook | blocks_structural_implementation for rule status, version, owner, evidence basis, and replay effects. | - | E14,E17 | P07,P09,P13,P15 |
| C6 | Concept identity and spine semantics | existing_adr | [ADR-0158](../adr/0158-concept-spine-multi-jurisdiction-reconciliation.md) | Concept spine carriers may proceed as per-run reconciled artifacts over governed namespaces. | - | E6,E7 | P02,P08,P10 |
| C7 | Legal authority, jurisdiction, and institutional competence | fast_track_adr | [ADR-0168](../adr/0168-legal-hierarchy-and-competence.md) | E9 legal competence work is blocked outside ADR-0168 hierarchy, fallback, authority-type, and competence-window semantics. | - | E9 | P05,P08,P10,P15 |
| C8 | Producer handshake protocol | existing_adr | [ADR-0159](../adr/0159-production-evidence-producer-contracts.md), [ADR-0158](../adr/0158-concept-spine-multi-jurisdiction-reconciliation.md) | Producer handoffs must expose consumed, emitted, rejected, and blocked bindings before downstream closeout. | - | E6,E7,E9-E12 | P02,P12 |
| C9 | Claim taxonomy and method compatibility | existing_adr | [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md), [ADR-0160](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md), [ADR-0159](../adr/0159-production-evidence-producer-contracts.md) | Claim-method bridges may proceed only when method authority is bound to ClaimRecord refs and negative method-mismatch tests exist. | - | E8,E12 | P02,P10,P14 |
| C10 | Counterfactual baselines and alternative comparison | existing_adr | [ADR-0160](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md) | Superiority claims require comparison evidence and cannot be projected from single-arm narrative support. | - | E8 | P10,P14,P15 |
| C11 | Numeric, time-role, and geographic semantics | existing_adr | [ADR-0158](../adr/0158-concept-spine-multi-jurisdiction-reconciliation.md), [ADR-0168](../adr/0168-legal-hierarchy-and-competence.md) | Time, unit, geography, and legal-window mismatches must transform, limit, split, or block; they cannot be metadata decoration. | - | E9,E10,E16 | P08,P10 |
| C12 | LLM boundary and candidate-to-authority firewall | new_adr_required | ADR-TBD-llm-candidate-authority-firewall | blocks_structural_implementation for any path where LLM formulation, critic, drafter, or repair output could become authority without producer admission. | - | E9-E12,E22 | P05,P10,P15 |
| C13 | Effective independence and evidence-line collapse | existing_adr | [ADR-0160](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md) | Strict collapse may proceed; graded weights and minima remain governed config and cannot be final authority thresholds. | - | E13,E22 | P10,P14 |
| C14 | Evidence conflict and counterevidence semantics | existing_adr | [ADR-0160](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md) | Conflict, rebuttal, limitation, and readiness caps must be first-class claim records, not hidden prose. | - | E8,E13,E22 | P10,P14 |
| C15 | Argument, warrant, and assurance profile semantics | existing_adr | [ADR-0156](../adr/0156-policy-design-case-runtime-quality-assurance-profile.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md) | Assurance graph work may proceed when claim, argument, warrant, rebuttal, counterevidence, and deficits remain inspectable. | - | E4,E5 | P03,P05,P10 |
| C16 | Multi-audience Policy Design Case surface semantics | existing_adr | [ADR-0162](../adr/0162-human-oversight-publication-external-audit-authority.md), [ADR-0150](../adr/0150-scorecard-readiness-approval-projection-boundaries.md) | Public, reviewer, expert, machine, dashboard, and audit views may project authority only with source refs and forbidden-use metadata. | - | E4,E5 | P03,P05,P10 |
| C17 | Contestability and disagreement formalism | fast_track_adr | [ADR-0170](../adr/0170-contestability-and-recourse-boundaries.md) | Contestability records may proceed; deployment appeal intake or adjudication remains outside PolicyOS core authority. | - | E4,E8,E22 | P03,P05,P09 |
| C18 | Tradeoff, welfare, and value-choice representation | new_adr_required | ADR-TBD-tradeoff-welfare-value-choice-provenance | blocks_structural_implementation for public welfare aggregation, social-weight provenance, and selected-frontier authority. | - | E4,E8 | P05,P10,P13 |
| C19 | Participation provenance and attribution | fast_track_adr | [ADR-0167](../adr/0167-participation-legitimacy-matrix.md) | Participation surfaces may proceed only with claim-use downgrade, provenance, dissent, and thin-consultation laundering tests. | - | E4,E11,E22 | P05,P10,P15 |
| C20 | Lifecycle dependency and revalidation semantics | existing_adr | [ADR-0163](../adr/0163-lifecycle-ddm-ex-post-calibration.md) | Lifecycle events may trigger scoped reissue and revalidation; historical records remain append-only. | - | E15,E16 | P02,P07,P08,P09 |
| C21 | Rule evolution, replay, and legacy retirement | existing_adr | [ADR-0163](../adr/0163-lifecycle-ddm-ex-post-calibration.md), [ADR-0100](../adr/0100-runtime-api-versioning-and-deprecation-policy.md) | Replay must preserve rule, taxonomy, concept, authority-profile, and code semantics for closed cases. | - | E14,E15 | P07,P08 |
| C22 | Evidence acquisition decision theory and VOI | fast_track_adr | [ADR-0166](../adr/0166-evidence-acquisition-decision-boundaries.md) | E17 acquisition work is blocked unless eligibility precedes VOI ranking and mandatory gates dominate. | - | E17 | P01,P05,P14,P15 |
| C23 | Run cost, budget, and degradation-SLA semantics | existing_adr | [ADR-0164](../adr/0164-run-cost-proportionality-evidence-budget-governance.md), [ADR-0149](../adr/0149-effective-mode-and-fallback-degradation-ledger.md) | Cost and degradation telemetry may inform readiness, but cost cannot silently waive evidence authority. | - | E18 | P09,P13 |
| C24 | Self-FMEA, soft-gate policy, review effectiveness, and complexity budget | fast_track_adr | [ADR-0169](../adr/0169-bounded-liveness-and-runtime-escalation.md), [ADR-0171](../adr/0171-review-effectiveness-telemetry-advisory-first.md) | Bounded liveness and advisory review telemetry may proceed; unbounded waits and immature telemetry blockers are forbidden. | - | E19 | P04,P09,P13 |
| C25 | Longitudinal calibration and balanced memory | existing_adr | [ADR-0172](../adr/0172-balanced-memory-influence-ledger.md), [ADR-0163](../adr/0163-lifecycle-ddm-ex-post-calibration.md) for calibration boundary | Balanced success, failure, and opportunity memory ledgers may proceed only as future influence records; historical priors never close current-run evidence. | - | E20,E21 | P07,P11,P15 |
| C26 | Evaluation methodology and semantic completeness | existing_adr | [ADR-0165](../adr/0165-formal-policy-case-substrate-invariant-specs.md), [ADR-0156](../adr/0156-policy-design-case-runtime-quality-assurance-profile.md) | Evaluation work may proceed only when semantic false-pass cases are distinct from constructor or checksum validity. | - | E1,E22,E24 | P10,P15 |
| C27 | Research synthesis and implementation readiness | no_adr_required | no_adr_required: implementation plan, W0.G, and this W0.H registry are docs and planning authority, not runtime architecture authority. | Does not block local docs planning; any runtime gate derived from readiness labels needs an ADR. | implementation_local | E23,E24 | P01,P06,P13 |
| C28 | Concept spine physical form | existing_adr | [ADR-0158](../adr/0158-concept-spine-multi-jurisdiction-reconciliation.md) | Hybrid governed namespaces plus per-run reconciled spine artifact is ratified; standalone registry service promotion is not. | - | E6,E7,E9-E13 | P02,P08 |
| C29 | Effective independence function | existing_adr | [ADR-0160](../adr/0160-evidence-portfolio-independence-multiverse-synthesis.md) | Strict collapse can be implemented; graded scores, weights, and portfolio minima remain governed config behind evidence. | - | E13,E22 | P13,P14 |
| C30 | Semantic benchmark rubric | new_adr_required | ADR-TBD-semantic-benchmark-rubric-and-gold-card-governance | blocks_structural_implementation for semantic gold-card labels, adjudication metadata, public-hidden-rotating packs, and automation rights. | - | E1,E22,E24 | P10,P15 |
| C31 | Acceptable deficits by authority level | fast_track_adr | [ADR-0166](../adr/0166-evidence-acquisition-decision-boundaries.md) | Deficit dispositions may proceed only when accepted deficit, publish with limitation, review, reissue, and hard block remain distinct. | - | E2,E3,E4,E19 | P04,P05,P09 |
| C32 | Complexity budget and ceremony boundary | no_adr_required | no_adr_required: numeric complexity budgets and Net-MAV weights are tuned_config_only; structural cost and proportionality context stays under ADR-0164. | Blocks final numeric thresholds only; advisory telemetry and governance-pruning reports may proceed as config. | tuned_config_only | E19 | P09,P13 |
| C33 | Rule evolution public policy | new_adr_required | ADR-TBD-rule-evolution-public-revalidation | blocks_structural_implementation for public annotation, mandatory revalidation, silent-upgrade bans, and requirement-id semantic remap policy. | - | E14,E15 | P03,P07,P08 |
| C34 | Participation legitimacy semantics | fast_track_adr | [ADR-0167](../adr/0167-participation-legitimacy-matrix.md) | Matrix structure and downgrade posture are ratified; final representativeness thresholds remain governed tuned parameters. | - | E4,E11,E22 | P05,P10,P15 |
| C35 | Calibration blocking thresholds | no_adr_required | no_adr_required: exact blocking thresholds are research_blocked until mature longitudinal evidence exists; advisory structure is bounded by ADR-0163 and ADR-0171. | Blocks final history-only blocking thresholds; sparse-history warnings and review routing may proceed. | research_blocked | E20,E21 | P10,P11,P15 |
| C36 | Capability debt algebra | no_adr_required | no_adr_required: W0.H uses debt labels for implementation-readiness reporting only; runtime or release blocking use requires a later ADR. | Does not block docs ratchet reporting; blocks authority-bearing release gates until ratified. | implementation_local | E0,E24 | P01,P13 |
| C37 | Bridge authority semantics | existing_adr | [ADR-0159](../adr/0159-production-evidence-producer-contracts.md), [ADR-0161](../adr/0161-claim-argument-warrant-compiler-closeout-gate.md), [ADR-0162](../adr/0162-human-oversight-publication-external-audit-authority.md) | Bridge and handoff records are authoritative only for boundary continuity and cannot replace producer evidence. | - | E3,E6,E7,E19 | P02,P05 |
| C38 | Obligation explosion control | existing_adr | [ADR-0173](../adr/0173-obligation-frontier-and-bundle-control.md) | Candidate ledger, bundle ledger, priority ceiling, and bounded blocking frontier semantics may proceed; numeric budget and Net-MAV weights remain governed config. | - | E17,E19 | P01,P13,P14,P15 |
| C39a | Projection structure and audience entitlement matrix | existing_adr | [ADR-0162](../adr/0162-human-oversight-publication-external-audit-authority.md), [ADR-0150](../adr/0150-scorecard-readiness-approval-projection-boundaries.md) | Typed projection may proceed when each audience surface exposes omissions, redactions, authority refs, and forbidden-use metadata. | - | E4,E5 | P03,P05 |
| C39b | Recourse mechanics | fast_track_adr | [ADR-0170](../adr/0170-contestability-and-recourse-boundaries.md) | High-stakes contested production publication is blocked without a verified reachable recourse pointer. | - | E4,E5,E15 | P03,P05,P09 |
| C40 | Producer coordination liveness | fast_track_adr | [ADR-0169](../adr/0169-bounded-liveness-and-runtime-escalation.md) | Producer waits require bounded states, deadlines, typed blockers, and escalation; no workflow may wait indefinitely. | - | E6,E7,E9-E13,E19 | P02,P09,P12 |
| C41 | Historical priors firewall | existing_adr | [ADR-0163](../adr/0163-lifecycle-ddm-ex-post-calibration.md), [ADR-0172](../adr/0172-balanced-memory-influence-ledger.md) | Historical priors may influence routing, budget, review, uncertainty, and future authority caps through typed influence records; they never close current-run evidence. | - | E20,E21,E22 | P11,P15 |

## Gate Interpretation

Rows marked `new_adr_required` are structural blockers. The named ADR may be
prepared in parallel with fixtures and code exploration, but mergeable runtime
structure must wait until the ADR is accepted and indexed.

Rows marked `no_adr_required` do not authorize hidden architecture. They narrow
scope:

- `implementation_local` rows are docs, test, or readiness-reporting mechanics.
  They may not become runtime authority without a later ADR.
- `tuned_config_only` rows are thresholds, weights, budgets, deadlines, or
  numeric defaults. They need owner, version, evidence, rollback, and promotion
  posture, not a new structural ADR unless the decision rule changes.
- `deployment_owned` rows would belong to a concrete institution or deployment,
  not the core PolicyOS runtime. W0.H currently records deployment ownership
  through ADR-0170 rather than a standalone C-row rationale.
- `research_blocked` rows may remain advisory, warning-only, or fixture-backed
  until empirical evidence can support a governed promotion.

## Pattern Pass

Relevant patterns: `P01`, `P03`, `P05`, `P06`, `P07`, `P08`, `P09`, `P10`,
`P11`, `P12`, `P13`, `P14`, and `P15`.

Existing anti-pattern found: the implementation plan already contains rich
C/E/P tables. Without this registry, those tables could become an implicit
architecture decision source and recreate `P01` contract-only capability,
`P05` authority dilution, `P06` ownership ambiguity, and `P15` candidate or
projection laundering.

Target correct pattern: structural implementation cites accepted ADRs,
fast-track ADRs, named future ADR blockers, or explicit no-ADR rationale before
schemas and gates harden.

Capability reality for `W0.H`:

| Capability element | W0.H proof |
| --- | --- |
| Typed artifact/contract | This registry page defines the allowed registry classes, rationale labels, and C0-C41 decision-source table. |
| Producer | Docs and ADR owners maintain the registry when C/E/P plans or ADR status changes. |
| Persisted artifact/event | The registry is persisted at `docs/reference/policy-design-case-structural-adr-registry.md`. |
| Orchestration bridge | The implementation plan, W0.G source ownership, W1.E evidence paths, W5.E operator guide, rollout runbook, ADR index, docs index, and documentation inventory cross-link this registry. |
| Consumer | Wave 0 exit, `I0`, `E23`, `E24`, ADR authors, implementers, code reviewers, W5 operators, and release reviewers use the table to reject uncited structural work. |
| Verification | `tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py` verifies C0-C41 coverage, ADR existence, fast-track ADR templates, cross-links, and local-path rejection. |
| Surface | `docs/reference/index.md`, `docs/reference/documentation-inventory.md`, and the MkDocs reference nav expose this page. |
| Negative/e2e semantic test | The regression test fails when any structural C-row lacks a decision source, a new-ADR blocker, or an explicit no-ADR rationale. |

Missing capability labels after this phase: none for W0.H as a decision-source
registry. It does not implement runtime Policy Design Case behavior, so later
capabilities must still prove their own producer, artifact, bridge, consumer,
surface, verification, and semantic test chain.

## Maintenance Rule

When a later wave changes a C-row's implementation posture:

1. Prefer updating the cited ADR or writing the named new ADR.
2. Regenerate ADR indexes if an ADR status or file changes.
3. Update this registry in the same change that relies on the decision.
4. Keep tuned values out of structural commitments unless the ADR cites
   calibration evidence and an owner.
5. Keep deployment-owned recourse or SLA authority outside core PolicyOS unless
   a deployment-specific ADR or runbook accepts that ownership.
6. Keep W5.E operator routes current in
   `docs/reference/policy-design-case-operator-guide.md` and
   `docs/runbooks/policy-design-case-rollout-rollback.md` when ADR authority,
   tuned-config posture, or rollout procedure changes.
