# ADR-0167: Participation Legitimacy Matrix

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution must distinguish evidence that people
were heard from evidence that a claim about an affected population is
admissible. Consultation notes, testimony, hearings, surveys, expert
interviews, civil-society submissions, and analyst or LLM summaries can all be
useful, but they do not carry the same authority.

The research synthesis for C19 and C34 concluded that the open question is no
longer whether participation evidence matters. The missing decision is how
PolicyOS bounds the claim use that participation provenance can support.
Without a fixed matrix, a thin consultation could be projected as broad
affected-population prevalence, a dissent record could be averaged away, or an
LLM-authored summary could be laundered into participation authority.

The repository already has the adjacent authority surfaces: policy intent and
affected-stakeholder fields, producer evidence contracts, claim binding,
evidence portfolio independence, publication authority, acquisition routing,
and public/reviewer/machine projection requirements. This ADR ratifies W0.B
FT-ADR-02 from the Universal Policy Design Case implementation plan so E4/E5,
E11, and E22 can implement participation surfaces without reopening the
structural boundary.

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

1. Participation legitimacy is evaluated through the structural matrix
   `claim_use x authority_level x population_scope`.
2. The first supported `claim_use` values are `prevalence`, `existence`,
   `qualitative`, `role-feasibility`, `dissent`, and `context-only`.
3. The first supported `authority_level` values are `research`, `governed`,
   and `production`, aligned with the existing policy authority profile rather
   than a new high-stakes axis.
4. The first supported `population_scope` values are `individual_or_case`,
   `affected_subgroup`, `affected_population`, and `general_population`.
5. Each participation artifact must compute a maximum allowed claim use from
   source kind, provenance class, process fields, population scope, and
   authority level before any projection, Scholar adapter claim, or semantic
   evaluation can treat it as support.
6. The default posture is fail-safe downgrade. If provenance is incomplete,
   mismatched, or uncertain, the claim use is downgraded to the strongest
   supported lower use, emitted as a limitation or blocker when required, and
   never silently promoted.
7. Population prevalence requires a representative or explicitly modeled
   representative survey basis for the claimed population scope. Consultation,
   hearing, testimony, expert interview, civil-society submission, or
   self-selected participation can support existence, qualitative context,
   role-feasibility, dissent, or context-only claims only when their provenance
   justifies that use.
8. Legitimacy and procedural-fairness projections are composite process
   claims. They require affected-group mapping, timing before policy lock-in,
   invitation or exclusion evidence, sponsor/facilitation disclosure,
   response-to-comment or effect trace, dissent preservation, and public
   limitations. They are not inferred from the mere existence of participation.
9. Dissent is a first-class participation outcome. Material unresolved dissent
   must be carried as contestation or limitation, not averaged into a single
   support score unless an accepted synthesis rule explicitly permits that
   aggregation for the requested use.
10. LLM or analyst participation summaries are candidate context only. They may
    help identify gaps or draft summaries, but they cannot satisfy affected
    person preference, prevalence, legitimacy, feasibility, or dissent slots
    without real participation provenance.

## Structural Commitment

The implementation must model participation records with at least these
structural fields:

- `participation_ref`
- `claim_refs`
- `claim_use_requested`
- `claim_use_allowed`
- `authority_level`
- `population_scope`
- `affected_group_map`
- `source_kind`
- `consultation_mode`
- `provenance_class`
- `representativeness_class`
- `sampling_or_recruitment_frame`
- `instrument_or_briefing_ref`
- `facilitation_or_sponsor_ref`
- `event_time`
- `policy_lock_in_time`
- `geography_scope`
- `consent_redaction_state`
- `aggregation_method`
- `dissent_state`
- `response_to_comment_ref`
- `limitations`
- `downgrade_reason`
- `blocker_ref`
- `public_projection_effect`
- `rule_version`

The first provenance classes are:

| Class | Meaning | Maximum ordinary use |
| --- | --- | --- |
| `A_representative_population` | Representative or explicitly modeled survey basis whose sample frame matches the claimed population scope. | `prevalence` for the matched scope, plus lower uses. |
| `B_structured_deliberative_or_process` | Deliberative or consultation process with disclosed recruitment, facilitation, briefing, affected-group mapping, and dissent handling. | Legitimacy/procedural process claims and considered qualitative acceptability, not raw prevalence unless class A is also met. |
| `C_attributable_nonrepresentative` | Attributable testimony, hearing input, complaint, expert interview, or submission with consent/redaction and source context. | `existence`, `qualitative`, `role-feasibility`, `dissent`, or `context-only`, depending on source role. |
| `D_unverifiable_or_speculative` | Missing frame, method, identity, or real participation provenance; includes LLM/analyst speculation. | `context-only` candidate or participation gap. |

The structural matrix starts with these rules:

| Requested claim use | Minimum class for individual/case | Minimum class for affected subgroup | Minimum class for affected population or general population |
| --- | --- | --- | --- |
| `prevalence` | `A_representative_population` for the asserted scope | `A_representative_population` for the asserted subgroup | `A_representative_population` for the asserted population |
| `existence` | `C_attributable_nonrepresentative` | `C_attributable_nonrepresentative` with scope limitation | `C_attributable_nonrepresentative` only as existence of a reported view, not prevalence |
| `qualitative` | `C_attributable_nonrepresentative` | `C_attributable_nonrepresentative` with affected-group mapping | `B_structured_deliberative_or_process` or downgrade to scoped qualitative context |
| `role-feasibility` | `C_attributable_nonrepresentative` for role-bound expert or affected-person evidence | `C_attributable_nonrepresentative` with role and scope stated | `B_structured_deliberative_or_process` or downgrade to role-scoped feasibility |
| `dissent` | `C_attributable_nonrepresentative` | `C_attributable_nonrepresentative` with safe projection | `C_attributable_nonrepresentative` as dissent existence; prevalence of dissent requires class A |
| `context-only` | `D_unverifiable_or_speculative` | `D_unverifiable_or_speculative` | `D_unverifiable_or_speculative` |

Authority level composes with this matrix:

| Authority level | Missing or thin participation with no affected-person claim | Missing or thin participation when affected-person claim is requested |
| --- | --- | --- |
| `research` | May publish as research-only with visible limitation. | Downgrade to supported claim use, emit accepted deficit, or block the affected claim. |
| `governed` | May publish with limitation only when the authority profile permits it and a reviewer can inspect the gap. | Downgrade or block legitimacy/prevalence claims unless required provenance exists. |
| `production` | Publication requires a narrow limitation, owner, and revalidation/participation plan when participation is material. | Hard block for population prevalence or legitimacy claims until required provenance exists. |

No reader may infer `claim_use_allowed` from source kind alone. The allowed use
must be derived from source kind, provenance class, representativeness class,
population scope, process fields, and authority level.

## Tuned Parameter

The matrix structure is fixed by this ADR. Numeric and deployment-specific
representativeness thresholds are governed configuration, not structural truth.

The following remain tuned parameters:

- sample-size, response-rate, margin-of-error, nonresponse, weighting, and
  coverage thresholds;
- minimum subgroup coverage and quota/stratification cutoffs;
- model-validation requirements for nonprobability or modeled samples;
- minimum process-participation breadth for legitimacy claims;
- reviewer, consultation, survey, and agency-request owners by deployment;
- deadlines for remediation or revalidation participation plans;
- privacy/redaction thresholds for public projection bands.

Tuned participation configuration must carry owner, version, default source,
status, feature/advisory posture, rollback path, and promotion evidence.
Changing a tuned threshold does not require a new ADR if the
`claim_use x authority_level x population_scope` structure and fail-safe
downgrade posture remain unchanged.

## Authority Boundary

Participation records are authority-bearing only for the participation facts
they can prove.

A participation record may be authoritative for:

- who or which role/group participated;
- when and how participation occurred;
- which population or affected-group scope was invited, represented, excluded,
  or missing;
- the source kind, provenance class, representativeness class, and process
  fields;
- what claim use was requested, allowed, downgraded, limited, or blocked;
- the existence of testimony, objection, dissent, role-bound feasibility
  evidence, or contextual input;
- whether a public projection must show limitation, dissent, or participation
  gap.

A participation record may not be authoritative for:

- prevalence outside its represented population scope;
- legitimacy or procedural fairness without process evidence;
- legal authority, data authority, method validity, closeout pass, or
  publication authority;
- Scholar publication prevalence or general affected-person preference;
- LLM/analyst speculation as real participation evidence;
- forced consensus when unresolved dissent remains material.

Public, reviewer, expert, machine, Scholar, and semantic-evaluation consumers
must enforce `claim_use_allowed`. Projection or package surfaces may display
participation facts and limitations, but they may not mint a stronger
participation claim than the record authorizes.

## Negative Laundering Test

Future implementation must include tests with these minimum cases:

1. A `prevalence` claim for `affected_population` at governed or production
   authority with only a thin consultation summary is downgraded, limited, or
   blocked. It cannot support affected-population prevalence.
2. A consultation summary with no sampling frame, no recruitment disclosure,
   and no underlying method emits `summary_without_underlying_method` or an
   equivalent typed blocker for prevalence and legitimacy.
3. A credible affected-person testimony can support existence or qualitative
   lived-experience claims, but attempting to project it as subgroup or
   affected-population prevalence fails closed.
4. A role-bound expert interview can support role-feasibility for that role
   only; it cannot become affected-person preference.
5. Unresolved dissent remains visible as dissent or contestation in reviewer
   and machine surfaces, and public projection cannot hide it by omission.
6. LLM or analyst speculation remains `context-only` or
   `candidate_unverified` until real participation provenance exists.

The canonical negative laundering test for this ADR is:

```text
claim_use = prevalence
authority_level = production
population_scope = affected_population
source_kind = consultation
provenance_class = C_attributable_nonrepresentative
representativeness_class = nonrepresentative
expected = closeout_block or downgrade_to_context/qualitative with public limitation
forbidden = affected-population prevalence support
```

## Feature Flag / Advisory Posture

Initial implementation is governed-config and advisory-first:

- `universal_pdc_participation_matrix`: may compute allowed claim use,
  downgrades, blockers, and limitations.
- `universal_pdc_participation_projection`: disabled for public/dashboard/API
  promotion until E4/E5 truth-preserving projection tests pass.
- `universal_pdc_participation_scholar_claims`: disabled for affected-person
  or participation-like Scholar claim support until E11 enforces provenance
  ceilings.
- `universal_pdc_participation_semantic_pack`: required before E22 can mark
  participation laundering scenarios covered.

Advisory mode may surface gaps, downgrades, and next actions. It cannot change
claim support, closeout, publication, or public projection state without the
relevant implementation reader and authority profile.

## Revision Path

A new ADR is required to:

- remove `claim_use x authority_level x population_scope` as the governing
  structure;
- allow prevalence without representative or explicitly modeled scope-matched
  evidence;
- allow consultation, testimony, hearing, expert interview, or self-selected
  input to satisfy affected-population prevalence by default;
- treat LLM or analyst speculation as authority-bearing participation evidence;
- permit unresolved dissent to be hidden from reviewer or machine surfaces;
- make a participation projection or Scholar/publication artifact mint
  stronger authority than the underlying participation record;
- weaken production hard-block behavior for participation prevalence or
  legitimacy claims without a replacement mandatory gate.

A governed config change is sufficient to tune numeric representativeness
thresholds, privacy projection bands, owner routing, deadlines, or
method-specific validation rules when the structural commitments above remain
intact.

## Affected E Tasks

This ADR unblocks:

- E4 Typed PDC Projection, for participation facts, downgrades, limitations,
  blockers, dissent, and audience-specific redaction;
- E5 Client/Dashboard/Export, for public, reviewer, expert, and machine
  participation surfaces that preserve claim-use ceilings;
- E11 Scholar Adapter, for participation-like or affected-person claims that
  must distinguish publication, source family, role evidence, and
  representativeness;
- E22 Semantic Evaluation, for false-pass and laundering fixtures covering
  participation prevalence, legitimacy, dissent, and LLM speculation.

It also constrains:

- E3 closeout, because participation deficits may block only the affected claim
  use or population scope;
- E13 portfolio aggregation, because participation source counts must not
  inflate independence or prevalence;
- E17 acquisition planning, because missing participation may route to survey,
  consultation, accepted deficit, downgrade, or block according to ADR-0166;
- E20/E21 calibration and memory, because participation outcomes may influence
  future routing but never become current-run evidence without provenance.

## Validation

The ADR itself is validated by docs lifecycle gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Future implementation must add unit, integration, and semantic tests proving:

- `claim_use_allowed` is computed before projection, Scholar support, or
  closeout effects;
- representativeness thresholds are read from governed configuration;
- thin consultation cannot support affected-population prevalence;
- missing participation blocks, limits, accepts a deficit, or downgrades only
  according to authority level and population scope;
- dissent and participation gaps remain visible in reviewer/machine surfaces;
- LLM/analyst summaries cannot satisfy participation evidence slots.

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. The existing authority profile,
claim-binding, producer-contract, public-projection, acquisition, and evidence
portfolio surfaces are the correct owners. This ADR adds the participation
decision boundary that those later surfaces consume; it does not create a
parallel participation runtime.

Relevant anti-patterns:

- P03 poor external surface: E4/E5 must expose participation quality, gaps,
  dissent, downgrades, and public limitations.
- P05 authority dilution: projection, Scholar hits, consultation summaries, or
  LLM summaries cannot mint participation authority.
- P10 structural-only validation: E22 must include semantic laundering tests,
  not only field-presence checks.
- P12 producer fragmentation: participation-like claims from Scholar,
  consultation, survey, and public input need a shared claim-use ceiling.
- P13 contract gravity well: numeric representativeness thresholds stay
  governed config rather than universal hardcoded gates.
- P14 raw evidence count inflation: repeated participation events or channels
  cannot inflate prevalence or independence when the sample frame is shared.
- P15 LLM speculation laundering: LLM/analyst summaries remain context-only
  candidates until real participation provenance exists.

Existing anti-pattern found: participation semantics were present in research
and plan prose but not yet an accepted ADR that E4/E5, E11, and E22 could cite.
That was `contract_only` as a decision dependency.

Target correct pattern: an accepted structural ADR with consumer-side
enforcement requirements, governed tuned parameters, visible limitations, and
negative semantic tests.

Missing capability labels after this ADR: `producer_missing`,
`bridge_missing`, `consumer_missing`, `surface_missing`, and
`semantic_test_missing`. Those labels are expected for W0.B because this phase
is a design decision, not the runtime producer or projection implementation.

Acceptance signal: later work can cite ADR-0167, compute `claim_use_allowed`
before consumer use, and prove with a negative test that thin consultation
cannot support affected-population prevalence.

## Consequences

Positive:

- Participation evidence can be useful without being overclaimed.
- Downstream surfaces get a stable participation authority ceiling.
- Dissent, missing groups, and process limits remain visible instead of being
  converted into narrative confidence.
- Numeric thresholds can mature through governed methodology work without
  changing the structural contract.

Negative:

- Some plausible public narratives will downgrade or block until a survey,
  process record, or participation remediation exists.
- E4/E5, E11, and E22 must implement consumer-side enforcement rather than
  relying on source labels.
- Public projection must be careful about privacy-safe participation disclosure.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- participation provenance and legitimacy record fields;
- deterministic `claim_use_allowed` computation;
- governed config for representativeness thresholds;
- closeout/readiness/public-projection readers for participation downgrades,
  blockers, limitations, and dissent;
- Scholar adapter checks for participation-like claims and source-role
  ceilings;
- semantic fixtures for thin-consultation prevalence laundering, testimony
  prevalence laundering, expert-role laundering, dissent omission, and LLM
  speculation laundering.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Extends: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
- Extends: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
- Extends: ADR-0162 Human Oversight, Publication, And External Audit
  Authority.
- Related: ADR-0166 Evidence Acquisition Decision Boundaries.
