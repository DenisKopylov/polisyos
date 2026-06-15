---
title: Policy Design Case Source Ownership
status: active
owner: team-policyos-runtime
created: 2026-05-22
source_research_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
source_synthesis: ../backlog/universal-policy-design-case-research-results-consolidation.md
raw_research_ledger: ../research/universal-policy-design/deep-research-reports-105-146-combined.md
implementation_plan: ../plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
failure_patterns: policy-design-case-failure-patterns.md
evidence_paths: policy-design-case-evidence-paths.md
operator_guide: policy-design-case-operator-guide.md
rollout_runbook: ../runbooks/policy-design-case-rollout-rollback.md
---

# Policy Design Case Source Ownership

Owner: `team-policyos-runtime`
Source of truth: `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`, `docs/backlog/universal-policy-design-case-research-results-consolidation.md`, `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`, and `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`

This page is the W0.G source-ownership surface for the universal Policy Design
Case program. It records the repo-owned chain from raw research to normalized
synthesis, research tasks, implementation gates, ADRs, and public docs
navigation.

The point is not archival neatness. Later C/E/P tasks must be able to cite a
repository path, owner, authority boundary, and verification path instead of a
local Downloads file, chat note, or unstaged workspace scratchpad.

## Canonical Source Chain

| Layer | Repo-owned path | Owner | Authority boundary | Consumers |
| --- | --- | --- | --- | --- |
| Raw research ledger | `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md` | `team-policy-design-research` | Historical source detail only; not the normalized engineering authority. | Synthesis, detail checks, future audit of research provenance. |
| Normalized synthesis | `docs/backlog/universal-policy-design-case-research-results-consolidation.md` | `team-policyos` | Controlling normalized summary for C0-C41 findings and decision backlog. | Research plan, implementation plan, ADR authors, Wave 0 gates. |
| Research plan | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md` | `team-policy-design-research` | Research-task contract and conceptual gate map; not runtime code authority. | Implementation plan, E task handoff, remaining research backlog. |
| Implementation plan | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md` | `team-policyos-runtime` | Engineering sequencing and wave gates; not runtime evidence. | Wave work, I0-I6 integration barriers, validation ladder. |
| Failure-pattern register | `docs/reference/policy-design-case-failure-patterns.md` | `team-policyos-runtime` | Shared anti-pattern lens and missing-state labels. | Plans, ADRs, reviews, closeout summaries. |
| ADR corpus | `docs/adr/index.md`, `docs/adr/index.toml`, and `docs/adr/**` | `team-policyos-runtime` | Structural decision authority. ADRs can ratify boundaries; they cannot replace producer evidence. | Gated implementation tasks, review, docs and runbook updates. |
| Fast-track Wave 0 ADRs | `docs/adr/0166-evidence-acquisition-decision-boundaries.md`, `docs/adr/0167-participation-legitimacy-matrix.md`, `docs/adr/0168-legal-hierarchy-and-competence.md`, `docs/adr/0169-bounded-liveness-and-runtime-escalation.md`, `docs/adr/0170-contestability-and-recourse-boundaries.md`, `docs/adr/0171-review-effectiveness-telemetry-advisory-first.md` | `team-policyos-runtime` | Ratified structural boundaries for acquisition, participation, legal competence, bounded liveness, contestability/recourse, and review telemetry. | Wave 0 gates, E4/E5/E9/E10/E15/E16/E17/E19/E22 planning, W0.H structural ADR registry. |
| Structural ADR registry | `docs/reference/policy-design-case-structural-adr-registry.md` | `team-policyos-runtime` | W0.H decision-source map from every C0-C41 structural decision to existing ADR, fast-track ADR, named new ADR blocker, or explicit `no_adr_required` rationale. | Wave 0 exit, I0 traceability, E23/E24 docs gates, ADR authors, implementation reviewers. |
| Evidence path ledger | `docs/reference/policy-design-case-evidence-paths.md` | `team-policyos-runtime` | W1.E canonical paths for raw sources, synthesis, ADR authority, validation commands, command evidence, and closeout notes. | W1 exit, E23 docs gates, operators, closeout authors, W5.E runbook authors. |
| Operator guide | `docs/reference/policy-design-case-operator-guide.md` | `team-policyos-runtime` | W5.E operator lookup for ADRs, system-design decision indexes, public evidence paths, tuned-parameter owners, validation ladders, capability evidence, and rollout/rollback procedures. | Operators, release reviewers, W5/W6 closeout authors, future agents. |
| Rollout and rollback runbook | `docs/runbooks/policy-design-case-rollout-rollback.md` | `@platform-owners` with `team-policyos-runtime` | W5.E procedure for promotion, hold, rollback, kill-switch, tuned-config downgrade, evidence preservation, and closeout-note recording. | Operators, incident commanders, release owners, governance reviewers. |
| Docs index | `docs/reference/index.md` and `docs/reference/documentation-inventory.md` | `@docs-owners` | Discoverability and operations routing. | Future agents, maintainers, operators, docs gates. |

## Repo Path Rule

All critical Policy Design Case source references must use repository-relative
paths under `docs/`, `src/`, `tests/`, `architecture/`, `schemas/`,
`packages/`, or `apps/`.

Do not use local-only source paths such as home-directory Downloads paths,
absolute workstation paths, browser tab notes, or temporary chat/workspace
notes as a critical implementation source. `_build/.tmp/` may hold command
output while a task is in progress, but accepted summaries, gates, and
traceability records must point back to repo-owned paths.

Raw research citations embedded inside the ledger remain historical source
detail. They are not enough for implementation authority unless they are
normalized through the synthesis or ratified by an ADR.

## C/E/P And Gate Traceability

| Ref | Source ownership role | Gate or consumer |
| --- | --- | --- |
| `C0` | Capability baseline and canonical paths start from repo-owned source and canonical module anchors. | `W0.G`, `W1.A`, `W1.E` |
| `C27` | Implementation readiness depends on ADRs, source traceability, and validation ladder paths. | `W0.H`, `E23`, `E24` |
| `E23` | Documentation, ADRs, runbooks, and public evidence paths keep source ownership durable. | `W0.G`, `W1.E`, `W5.E` |
| `E24` | Final implementation plan and validation ladder must cite repo-owned research and ADR sources. | `W0.G`, Wave 6 |
| `P03` | External/docs surfaces must expose what the system knows, including source provenance. | Docs index and documentation inventory |
| `P06` | Canonical ownership ambiguity is closed by repo paths and generated/indexed ADR surfaces. | W0.G source chain and source-ownership test |
| `P13` | Governance remains proportional by keeping W0.G to path ownership, authority boundaries, and a narrow regression check. | `W1.E` and `W5.E` continue deeper docs/runbook work |
| `P15` | LLM or raw-draft content remains candidate/detail until normalized or ratified. | Synthesis and ADR authority boundaries |
| `I0` | ADR/source traceability proves raw source, synthesis, C/E/P ids, and gated tasks are queryable. | Wave 0 exit |
| `W0.G` | This page, source-chain front matter, docs index links, and regression test make source ownership explicit. | `tests/repo_quality/tools/test_policy_design_case_source_ownership.py` |
| `W0.H` | `docs/reference/policy-design-case-structural-adr-registry.md` prevents C0-C41 structural decisions from being silently baked into implementation tables without ADR authority or explicit no-ADR rationale. | `tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py` |
| `W1.E` | `docs/reference/policy-design-case-evidence-paths.md` prevents command evidence and closeout notes from drifting into local files, hidden notebooks, or social memory. | `tests/repo_quality/tools/test_policy_design_case_documentation_paths.py` |
| `W5.E` | `docs/reference/policy-design-case-operator-guide.md` and `docs/runbooks/policy-design-case-rollout-rollback.md` make ADR lookup, system-design decision context, tuned owners, validation ladders, capability evidence, and rollout/rollback paths operationally durable. | `tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py` |

## Pattern Pass

Relevant patterns: `P03`, `P06`, `P13`, and `P15`.

Existing anti-pattern found: the raw ledger intentionally preserves historical
research notes, including places where an earlier research pass could not see
the current repo state. If future implementation cites those notes directly as
authority, that becomes P06 ownership ambiguity and can become P15 candidate
laundering.

Target correct pattern: raw detail stays repo-owned but subordinate to the
normalized synthesis, implementation plan, ADR index, this source ownership
surface, and the W1.E evidence-path ledger.

Capability reality for W0.G:

| Capability element | W0.G proof |
| --- | --- |
| Typed artifact/contract | This source-ownership reference page and source-chain front matter in the linked plans. |
| Producer | Docs/source owners maintain the source chain through repo docs and ADR generation. |
| Persisted artifact/event | Source chain is persisted under `docs/reference/`, `docs/research/`, `docs/backlog/`, `docs/plans/active/`, and `docs/adr/`. |
| Orchestration bridge | Research plan, synthesis, implementation plan, fast-track ADRs, docs index, and documentation inventory cross-link the same repo paths. |
| Consumer | Wave 0 exit, I0, E23, E24, future ADR authors, future implementers, and docs reviewers. |
| Verification | `tests/repo_quality/tools/test_policy_design_case_source_ownership.py` checks required repo paths, cross-links, forbidden local path patterns, and C/E/P/I0/W0.G coverage. |
| Surface | `docs/reference/index.md` and `docs/reference/documentation-inventory.md` expose this page. |
| Negative/e2e semantic test | The regression test rejects local download-directory or workstation paths and missing source-chain links in the canonical W0.G documents. |

Missing capability labels after this phase: none for source ownership itself.
Runtime PDC capabilities remain governed by their own phase labels and cannot
borrow authority from this docs surface.

## Maintenance Rule

When a future ADR, plan, runbook, or closeout summary cites universal Policy
Design Case research, it should cite the repo path at the correct layer:

1. Use the synthesis for normalized findings.
2. Use the raw ledger only for source-detail audits.
3. Use the research plan for C task intent.
4. Use the implementation plan for E task sequencing and gates.
5. Use ADRs for ratified structural decisions.
6. Use this page when the question is source ownership itself.
7. Use `docs/reference/policy-design-case-evidence-paths.md` when the question
   is command evidence, validation command placement, or closeout note paths.
8. Use `docs/reference/policy-design-case-operator-guide.md` when the question
   is how an operator finds ADRs, tuned owners, capability evidence, validation
   ladders, and rollout or rollback procedures.
9. Use `docs/runbooks/policy-design-case-rollout-rollback.md` when the question
   is a concrete promotion, hold, rollback, or kill-switch action.
