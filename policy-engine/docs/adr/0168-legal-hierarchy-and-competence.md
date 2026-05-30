# ADR-0168: Legal Hierarchy And Competence Boundaries

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution needs Lex to answer a sharper question
than "did retrieval find a norm in the same jurisdiction or topic?" Serious
policy recommendations need to know whether a norm can carry the requested
legal authority for a claim, actor, instrument, time window, implementation
path, and fiscal action.

The repository already has relevant surfaces: Lex query normalization and
applicability reports, `lex/api.py`, legal-to-DAG mapping records, the concept
and jurisdiction spine, production evidence producer contracts, policy intent
authority profiles, semantic binding, scorecard/readiness boundaries, and
acquisition decision boundaries. The missing decision is the legal competence
boundary that prevents global or broad jurisdiction/topic retrieval from being
promoted into recommendation-level legal authority.

Without this ADR, E9 could recreate the PolicyOS failure mode where a generic
legal hit looks useful but lacks competence, hierarchy, instrument, time,
implementation, or fiscal authority. That would dilute authority, conflate time
roles, and let candidate legal context satisfy claim-level legal slots.

This ADR ratifies W0.D FT-ADR-04 from the Universal Policy Design Case
implementation plan.

Source traceability is repo-owned:

- raw ledger:
  `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
- normalized synthesis:
  `docs/backlog/universal-policy-design-case-research-results-consolidation.md`
- research plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`
- implementation plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`
- W0.G source ownership:
  `docs/reference/policy-design-case-source-ownership.md`

## Decision

1. Lex legal outputs must distinguish generic legal context from serious legal
   authority. Generic jurisdiction, topic, or corpus matches are at most
   `context_only` or `candidate_norm`; they cannot satisfy a governed or
   production legal obligation.
2. Serious legal authority requires a claim-level legal competence record that
   binds a source norm to:
   - `claim_ref`;
   - `norm_ref` and provenance;
   - `authority_basis`;
   - one or more `authority_types`;
   - competent actor or institution;
   - permitted policy instrument;
   - implementation authority;
   - fiscal authority when spending, revenue, procurement, grant, or budget
     authority is claimed;
   - jurisdiction and hierarchy position;
   - per-jurisdiction fallback policy reference;
   - legal as-of time and legal effective window;
   - policy effective window or requested implementation window;
   - preemption, conflict, supersession, and limitation state;
   - contestability, appeal, or review path when required by the authority
     profile.
3. The initial legal admissibility grades are:
   `context_only`, `candidate_norm`, `selected_authority`,
   `limited_authority`, `contested_authority`, and `blocked_no_authority`.
4. Jurisdiction fallback is governed per-jurisdiction namespace configuration.
   There is no universal fallback rule such as "use parent jurisdiction" or
   "use national law when local law is missing." If a jurisdiction lacks
   fallback configuration for the requested authority type, serious legal
   authority fails closed to `blocked_no_authority` or `limited_authority`,
   depending on the authority profile and claim scope.
5. One norm may carry multiple authority types at the same time. The canonical
   authority-type facets are `implementing`, `delegating`, `enabling`,
   `funding`, `oversight`, and `appeals_or_contestability`.
6. Authority-type facets remain independently consumable. A norm that is
   enabling and oversight authority does not automatically become funding or
   implementation authority.
7. Competence changes split claims by legal window. When competence, hierarchy,
   delegation, preemption, effective date, fiscal authorization, or permitted
   instrument changes during the requested policy window, Lex must emit legal
   segments rather than one undifferentiated pass/fail result.
8. A competence gap blocks or limits only the affected legal segment unless the
   active authority profile requires whole-claim closure.
9. Legal time roles are not interchangeable. Lex records must distinguish
   `legal_as_of`, `legal_effective`, `policy_effective`,
   `implementation_period`, `fiscal_period`, `publication_time`, and
   `replay_time` when those roles are relevant.
10. LLM-generated legal summaries, topic labels, and retrieval rationales are
    candidates only. They may help route Lex work, but they cannot satisfy
    legal competence without deterministic or governed Lex validation and
    producer evidence.

## Structural Commitment

The Lex legal authority adapter must emit or persist at least these structural
fields for each serious legal anchor:

- `legal_authority_record_id`
- `claim_ref`
- `claim_segment_ref`
- `norm_ref`
- `norm_version_ref`
- `source_provenance_ref`
- `jurisdiction`
- `jurisdiction_fallback_policy_ref`
- `fallback_path`
- `fallback_disposition`
- `authority_basis`
- `authority_types`
- `competent_actor_ref`
- `hierarchy_position`
- `instrument_types`
- `implementation_authority_ref`
- `fiscal_authority_ref`
- `legal_as_of`
- `legal_effective_window`
- `policy_effective_window`
- `implementation_period`
- `fiscal_period`
- `preemption_state`
- `conflict_state`
- `supersession_state`
- `contestability_or_appeal_ref`
- `admissibility_grade`
- `selected_norm_refs`
- `rejected_norm_refs`
- `no_anchor_rationale`
- `blocker_ref`
- `limitation_ref`
- `rule_version_ref`
- `authority_profile_ref`
- `producer_artifact_ref`
- `reader_effect`

`fallback_path` is valid only when it is justified by
`jurisdiction_fallback_policy_ref`. A broad match without the listed facets must
remain `context_only` or `candidate_norm`.

The claim-window split record must include:

- `split_reason`
- `source_claim_ref`
- `legal_window_start`
- `legal_window_end`
- `segment_disposition`
- `segment_authority_types`
- `segment_blocker_ref`
- `segment_limitation_ref`
- `rejoin_policy`

`rejoin_policy` may combine legal segments only when the reader can preserve
the weakest segment disposition and public projection does not hide blocked,
limited, or contested windows.

## Tuned Parameter

These values are governed configuration, not structural truth:

- jurisdiction-specific fallback tables and ordering;
- fallback availability by authority type, policy instrument, or actor class;
- default legal reviewer or owner for each jurisdiction namespace;
- severity thresholds for when a conflict is limitation versus blocker;
- freshness windows for Lex corpus material;
- confidence cutoffs for candidate retrieval before competence evaluation;
- advisory-to-blocking rollout posture by authority level;
- public wording templates for legal limitations or no-anchor rationales.

Changing tuned parameters does not require a new ADR when the structural
boundary remains unchanged: generic matches still cannot satisfy serious legal
authority, fallback remains per-jurisdiction governed config, authority-type
facets remain independent, and competence changes still split by legal window.

## Authority Boundary

A Lex legal authority record may be authoritative for:

- whether a norm was selected, rejected, contested, limited, or absent for a
  claim or claim segment;
- which jurisdiction fallback policy was applied;
- which authority types the norm can carry;
- which actor, instrument, implementation, fiscal, hierarchy, and time facets
  were satisfied;
- why a legal segment is blocked, limited, or publishable with legal
  limitation;
- which legal rule version and corpus provenance supported the result.

A Lex legal authority record may not be authoritative for:

- empirical effectiveness;
- data source admissibility, lineage, quality, or freshness;
- budget availability beyond legal fiscal authority;
- method validity or simulation adequacy;
- participation legitimacy;
- public publishability independent of closeout and projection readers;
- appeal or recourse adjudication outcomes unless a separate deployment-owned
  process reports them.

Lex can establish that spending is legally authorized; it cannot prove funds
exist, are sufficient, or have been allocated unless another producer emits
that evidence.

## Negative Laundering Test

Future E9 implementation must include tests with these minimum cases:

1. A generic Ukrainian jurisdiction/topic match exists, but no competent actor,
   permitted instrument, legal effective window, or implementation authority is
   established. Lex must emit `context_only` or `blocked_no_authority`, not
   `selected_authority`.
2. A national enabling norm exists for a local program, but the per-jurisdiction
   fallback table does not allow national fallback for the requested local
   implementation authority. The claim segment fails closed instead of falling
   back through a universal hierarchy rule.
3. A norm carries `enabling` and `oversight` authority but no `funding`
   authority. A spending claim remains blocked or limited for funding even
   though the same norm may support non-fiscal legal context.
4. Competence transfers from one institution to another during the policy
   window. Lex must split the claim into legal windows and block or limit only
   segments whose competent actor or authority type is unresolved.
5. A stale norm was effective at publication time but superseded before the
   requested implementation period. Legal as-of, legal effective, publication,
   replay, and implementation time cannot be collapsed into one pass.
6. An LLM summary correctly describes a law but lacks a deterministic Lex
   norm/ref and competence record. The summary remains `candidate_norm` or
   `context_only` and cannot satisfy legal authority.

## Feature Flag / Advisory Posture

Initial implementation is advisory until E9 wires Lex producer artifacts into
claim records and closeout readers:

- `universal_pdc_lex_legal_competence_advisory`: may emit grades, blockers,
  limitations, and split recommendations without changing closeout state.
- `universal_pdc_lex_jurisdiction_fallback_config`: enables governed
  per-jurisdiction fallback table lookup.
- `universal_pdc_lex_competence_window_split`: enables claim splitting by legal
  window and exposes segment dispositions.
- `universal_pdc_lex_legal_authority_commit`: disabled for governed and
  production authority until producer artifacts, claim registry bridges,
  readers, public/audit surfaces, and semantic negative tests exist.

Advisory mode can inform reviewers and acquisition planning. It cannot publish
or close a claim unless the downstream authority profile and closeout readers
consume the Lex result.

## Revision Path

A new ADR is required to:

- allow generic jurisdiction or topic matches to satisfy serious legal
  authority;
- introduce a universal jurisdiction fallback rule;
- remove claim-window splitting for competence changes;
- collapse legal time roles into one timestamp for governed or production
  authority;
- treat one authority type as implying another by default;
- allow LLM-generated legal content to satisfy legal authority slots;
- let Lex legal authority records bypass claim registry, closeout, or public
  projection readers.

A config change is sufficient to adjust fallback tables, reviewer owners,
freshness windows, rollout posture, or conflict severity thresholds when the
structural boundaries above remain intact.

## Affected E Tasks

This ADR unblocks:

- E9 Lex Legal Authority Adapter.

It also constrains:

- E4 Typed PDC Projection, because legal limitations, blockers, contested
  authority, and no-anchor rationales must remain visible;
- E5 Client/Dashboard/Export, because external surfaces cannot turn legal
  context into legal authority;
- E7 NL/Replay Integration, because replay must preserve the legal rule version
  and time-role semantics that closed or blocked the claim;
- E13 Portfolio Aggregation, because shared legal authority is an independence
  collapse reason;
- E15 Lifecycle/Reissue, because legal changes can reissue only affected
  claim segments;
- E17 Acquisition Planner, because legal competence gaps route to legal corpus
  expansion, agency/governed review, limitation, or closeout block;
- E22 Semantic Evaluation, because legal laundering tests must include generic
  retrieval, stale norms, missing fiscal authority, missing implementation
  authority, and LLM legal summaries.

## Validation

The ADR itself is validated by docs lifecycle gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Future implementation must add unit, integration, or semantic tests proving:

- generic jurisdiction/topic retrieval cannot satisfy serious legal authority;
- fallback requires governed per-jurisdiction configuration;
- one norm can carry multiple independent authority types;
- missing funding, implementation, instrument, or competent-actor facets block
  only the affected authority slots;
- competence changes split claims by legal window;
- legal time roles are preserved through replay and public projection;
- Lex producer artifacts bind to ClaimRecord refs before closeout readers can
  use them.

## Capability Reality And Pattern Pass

This ADR closes the W0.D decision ambiguity, but it does not claim E9 runtime
completion. Until Wave 3 implements the Lex adapter, E9 remains
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
`surface_missing`, and `semantic_test_missing`.

Relevant failure patterns are:

- P01, because a legal authority contract is not enough without producer,
  bridge, reader, surface, and negative tests;
- P05, because legal context cannot be projected as legal authority;
- P08, because legal as-of, effective, policy, implementation, fiscal,
  publication, and replay time roles carry different authority;
- P12, because Lex must coordinate with the concept/jurisdiction spine and
  claim compiler before authority-bearing emission;
- P15, because LLM legal summaries remain candidates until Lex validates them.

## Consequences

Positive:

- Lex can provide useful legal context without overstating authority.
- E9 has a structural boundary for per-claim legal anchors, blockers,
  limitations, and no-anchor rationales.
- Jurisdiction fallback becomes auditable governed config rather than an
  invisible global assumption.
- A single norm can support several legal roles without collapsing those roles.
- Legal changes can reissue or limit only affected claim windows.

Negative:

- Some plausible policy requests will block until legal competence facets are
  resolved.
- Jurisdiction fallback tables need governed ownership and review.
- Lex records become richer and must be preserved through claim registry,
  closeout, projection, and replay surfaces.
- Public surfaces must explain legal limitations without turning them into
  authorization.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- Lex legal authority and competence records;
- per-jurisdiction fallback namespace config;
- claim-window split records for legal competence changes;
- selected, rejected, contested, limited, blocked, and no-anchor legal refs;
- authority-type facets for implementing, delegating, enabling, funding,
  oversight, and appeals-or-contestability authority;
- Lex-to-ClaimRecord bridge behavior;
- closeout/public/audit readers that preserve legal blocker and limitation
  semantics;
- negative semantic tests for generic retrieval, universal fallback,
  authority-type inference, stale legal time, competence-window splits, and LLM
  legal summary laundering.

## Related Decisions

- Extends: ADR-0051 Legal-to-DAG Mapping Types.
- Extends: ADR-0057 Legal bridge via lex/api.py, not separate legal_graph/
  module.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Extends: ADR-0158 Concept Spine And Multi-Jurisdiction Reconciliation.
- Extends: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Related: ADR-0166 Evidence Acquisition Decision Boundaries.
