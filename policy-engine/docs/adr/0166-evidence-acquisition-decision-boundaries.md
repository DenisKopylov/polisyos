# ADR-0166: Evidence Acquisition Decision Boundaries

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution needs a disciplined answer to a common
runtime question: when a claim lacks admissible evidence, what should PolicyOS
do next?

The repository already has strong adjacent primitives: DataGap as a first-class
object, Scientist VOI decision records, Fabric SourceContract, Lex retrieval,
Scholar retrieval, Data Forge snapshots, Foundry methods, run-cost governance,
evidence portfolios, lifecycle, and closeout. The missing decision is not
"should VOI exist?" or "what acquisition strategies are possible?" The missing
decision is that ranking is not authorization.

Without this ADR, a high-scoring strategy could be used to route around a
mandatory legal, data, method, participation, or closeout gate. That would
recreate the core failure pattern: a system that appears helpful while
laundering weak, proxy, broad-bundle, or LLM-generated material into
authority-bearing evidence.

This ADR ratifies W0.A FT-ADR-01 from the Universal Policy Design Case
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

1. Evidence acquisition is a decision-boundary layer above VOI. VOI ranks
   options only after eligibility has been determined.
2. The canonical acquisition strategies are:
   `public_registry`, `agency_request`, `survey`, `consultation`,
   `legal_corpus_expansion`, `academic_retrieval`,
   `production_snapshot_build`, `source_contract_remediation`,
   `proxy_with_degraded_authority`, `accepted_deficit`, `rerun`, and
   `closeout_block`.
3. Acquisition routing evaluates:
   `gap_type x authority_level x mandatory_gate_state -> eligible_strategies
   -> decision_owner`.
4. `mandatory_gate_state` has three initial values:
   `none`, `overridable_by_governed_commit`, and `non_overridable`.
5. Mandatory gates dominate VOI. A `non_overridable` gate can produce only
   required remediation or `closeout_block`, even if VOI ranks a proxy,
   deficit, or cheap retrieval path highly.
6. `accepted_deficit`, `publish_with_limitation`, and `closeout_block` are
   terminally different:
   - `accepted_deficit` means evidence cannot or should not be acquired now,
     and the missing evidence is explicit.
   - `publish_with_limitation` means publication is allowed only because the
     active authority profile permits the limitation and the limitation is
     externally visible.
   - `closeout_block` means closeout or publication cannot proceed in the
     requested scope.
7. `publish_with_limitation` never bypasses a mandatory gate. It is available
   only when the gate state and active authority profile explicitly permit it.
8. Research authority may allow automatic recommendation and routing for
   non-authority-bearing actions. Governed and production authority may allow
   automatic recommendation, but commit to proxy-with-degraded-authority,
   accepted deficit, or publish-with-limitation requires a governed/human
   decision owner.
9. Acquisition outcomes may feed VOI calibration, strategy priors, budget
   estimates, and future routing. They never become current-run evidence unless
   the selected producer emits an admissible, authority-enveloped artifact.
10. LLM-generated acquisition ideas are candidates only. They may propose
    strategies or identify likely gaps, but they cannot satisfy legal, data,
    method, participation, or closeout evidence slots.

## Structural Commitment

The implementation must model acquisition with at least these structural
fields:

- `gap_id`
- `gap_type`
- `claim_ref`
- `scenario_requirement_refs`
- `authority_level`
- `mandatory_gate_state`
- `eligible_strategies`
- `ineligible_strategies`
- `voi_ranking_ref`
- `recommended_strategy`
- `decision_owner`
- `commit_authority`
- `terminal_disposition`
- `limitation_ref`
- `accepted_deficit_ref`
- `blocker_ref`
- `producer_expected`
- `producer_output_ref`
- `calibration_feedback_ref`
- `public_projection_effect`

VOI can produce `voi_ranking_ref` only after `eligible_strategies` is computed.
No reader may infer eligibility from VOI rank.

The initial eligibility matrix is:

| Gap type | Research with no mandatory gate | Governed/production with no mandatory gate | Overridable gate | Non-overridable gate |
| --- | --- | --- | --- | --- |
| Legal corpus coverage | `legal_corpus_expansion`, `academic_retrieval`, `accepted_deficit`, `rerun` | `legal_corpus_expansion`, `agency_request`, `accepted_deficit`, `rerun` | `legal_corpus_expansion`, `agency_request`, `publish_with_limitation` only with legal owner | `closeout_block` or required legal remediation |
| Legal competence / authority | `legal_corpus_expansion`, `accepted_deficit` for research-only claims | `legal_corpus_expansion`, `agency_request` | governed legal owner may limit scope | `closeout_block`; survey/proxy cannot close |
| Scenario source family | `public_registry`, `academic_retrieval`, `proxy_with_degraded_authority`, `accepted_deficit` | `public_registry`, `agency_request`, `production_snapshot_build`, `source_contract_remediation`, `proxy_with_degraded_authority` with owner | governed owner may proxy or limit | `closeout_block` until admissible source family exists |
| Data snapshot / release | `production_snapshot_build`, `rerun`, `accepted_deficit` | `production_snapshot_build`, `rerun`, `agency_request` | governed owner may limit freshness/scope | `closeout_block` until official snapshot/read surface exists |
| Field, unit, time, geography, lineage, or quality facet | `public_registry`, `production_snapshot_build`, `proxy_with_degraded_authority`, `accepted_deficit` | `production_snapshot_build`, `agency_request`, `proxy_with_degraded_authority` with limitation | governed owner may transform, limit, or accept deficit | `closeout_block` when facet is mandatory for claim type |
| Method obligation | `rerun`, `academic_retrieval`, `accepted_deficit` | `rerun`, `academic_retrieval`, method remediation, human review | governed owner may accept method deficit or limit claim | `closeout_block` until named method obligation is met |
| Academic/scholar support | `academic_retrieval`, `accepted_deficit`, `rerun` | `academic_retrieval`, `agency_request`, `accepted_deficit` | governed owner may publish limitation | `closeout_block` only when authority profile makes scholar support mandatory |
| Participation / affected-person claim | `consultation`, `survey`, `accepted_deficit` | `consultation`, `survey`, `agency_request` | governed owner may downgrade claim use | `closeout_block` for prevalence/legitimacy claim that lacks required process |
| Counterevidence / rebuttal gap | `academic_retrieval`, `public_registry`, `rerun`, `accepted_deficit` | `academic_retrieval`, `agency_request`, `rerun`, `accepted_deficit` | governed owner may accept deficit with public limitation | `closeout_block` when rebuttal/counterevidence is mandatory |
| Cost/SLA or runtime degradation | `rerun`, `accepted_deficit`, `closeout_block` | `rerun`, `accepted_deficit`, `publish_with_limitation`, `closeout_block` | governed owner may continue with limitation | `closeout_block` when durability, replay, or closeout artifact production is broken |

`source_contract_remediation` is implemented through the Fabric/Data Forge
producer path. It is listed separately to make clear that broad source labels
or raw file availability do not satisfy scenario source-family contracts.

## Tuned Parameter

These values are governed configuration, not structural truth:

- VOI weights and net-VOI formula coefficients;
- expected cost, elapsed-time, provider-call, reviewer, and acquisition effort
  estimates;
- strategy priors and historical success rates;
- authority-level thresholds for when proxy evidence is permitted;
- freshness, sample-size, representativeness, and quality cutoffs used inside a
  strategy;
- default owners for deployment-specific agency request, consultation, or
  survey routes;
- timeout/retry limits for acquisition attempts.

Changing a tuned parameter does not require a new ADR if the structural
eligibility, terminal disposition, mandatory-gate, and authority-owner
semantics remain unchanged. Tuned parameters must carry owner, version,
default source, feature/advisory posture, rollback path, and promotion evidence.

## Authority Boundary

Acquisition records are routing and governance evidence. They are not domain
evidence.

An acquisition record may be authoritative for:

- which gap was detected;
- which strategies were eligible or ineligible;
- which VOI ranking was considered;
- who had commit authority;
- which terminal disposition was selected;
- which producer was asked to remediate or acquire evidence;
- how the outcome should feed future VOI calibration.

An acquisition record may not be authoritative for:

- legal authority;
- source-family satisfaction;
- data quality, lineage, freshness, or schema;
- method validity;
- participation representativeness;
- claim support;
- closeout pass.

Those authorities require producer artifacts and reader validation. A completed
acquisition action can only point to those artifacts; it cannot replace them.

## Decision Owner Matrix

| Authority level | Recommendation owner | Commit owner for ordinary acquisition | Commit owner for proxy, deficit, or publication limitation | Non-overridable blocker |
| --- | --- | --- | --- | --- |
| Research | runtime planner or Scientist workflow | runtime planner may commit if no publication authority is claimed | researcher or configured review owner | automatic `closeout_block` or research-only scope downgrade |
| Governed | runtime planner may recommend | governed workflow owner | governed/human decision owner required | automatic `closeout_block` until mandatory remediation |
| Production | runtime planner may recommend | production governance owner or delegated runtime policy | production governance/human decision owner required; public limitation required | automatic `closeout_block` until mandatory remediation |

The decision owner must be recorded before an acquisition recommendation can
change claim publication state, closeout state, or public projection state.

## Negative Laundering Test

Future implementation must include tests with these minimum cases:

1. Legal competence gap with `non_overridable` state and high VOI for
   `survey` or `proxy_with_degraded_authority` still returns `closeout_block`.
2. Scenario source-family gap for `production_msme_panel` where a broad
   `datasets` bundle exists still marks `datasets` ineligible for claim
   authority and recommends `source_contract_remediation` or block.
3. Production snapshot gap where raw files exist but no official snapshot/read
   surface exists returns `production_snapshot_build` or `closeout_block`, not
   `publish_with_limitation`, unless the authority profile explicitly permits
   the limitation.
4. Participation prevalence claim with thin consultation recommends downgrade,
   survey/consultation acquisition, or block; it cannot publish a prevalence
   claim with limitation unless the participation ADR and authority profile
   allow it.
5. LLM-generated acquisition recommendation remains `candidate_unverified`
   until an acquisition planner validates strategy eligibility and a producer
   emits an admissible artifact.

## Feature Flag / Advisory Posture

Initial implementation is advisory by default:

- `universal_pdc_acquisition_planner`: may emit acquisition records and next
  actions.
- `universal_pdc_acquisition_commit`: disabled until E17 implements governed
  commit paths and audit evidence.
- `universal_pdc_proxy_with_limitation_commit`: disabled for governed and
  production authority until explicit owner and public limitation surfaces
  exist.

Advisory mode may inform operators, reviewers, VOI calibration, and future
strategy priors. Advisory mode cannot change current-run closeout, publication,
or claim-support state without the relevant commit authority.

## Revision Path

A new ADR is required to:

- add or remove a terminal disposition;
- weaken a non-overridable gate;
- allow VOI to rank before eligibility;
- allow automatic governed/production commit for proxy, accepted deficit, or
  publish-with-limitation;
- let acquisition records satisfy domain evidence slots;
- change the authority meaning of `accepted_deficit`,
  `publish_with_limitation`, or `closeout_block`;
- remove the requirement that acquisition outcomes feed calibration only as
  future priors.

A config change is sufficient to tune costs, priors, thresholds, timeouts,
default owners, or strategy ranking weights, provided the structural rules in
this ADR remain intact.

## Affected E Tasks

This ADR unblocks:

- E10 Fabric Data Source And Scenario Contract Adapter, for acquisition paths
  triggered by missing source-family contracts or missing facets;
- E16 Data Forge Closeout Binding, for acquisition paths triggered by missing
  official snapshots, release manifests, read APIs, or lineage/quality gates;
- E17 Evidence Acquisition Planner, for the planner itself.

It also constrains:

- E13 portfolio aggregation, because acquisition cannot inflate evidence
  strength;
- E18 cost/budget/degradation gates, because acquisition budgets are tuned
  config and closeout inputs;
- E20/E21 calibration and memory, because acquisition outcomes become future
  influence signals only;
- E22 semantic evaluation, because laundering tests must include acquisition
  bypass attempts.

## Validation

The ADR itself is validated by docs lifecycle gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Future implementation must add unit or repo-quality tests proving:

- eligibility is computed before VOI ranking;
- VOI cannot bypass a non-overridable mandatory gate;
- terminal dispositions remain distinct in records, readers, and public
  surfaces;
- governed/production proxy, deficit, or limitation commit requires the
  configured decision owner;
- acquisition outcomes cannot enter claim evidence slots without producer
  artifacts and reader validation.

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. The existing DataGap, VOI, Fabric,
Lex, Scholar, Data Forge, run-cost, claim-binding, and closeout surfaces are
the right owners. This ADR adds the acquisition decision boundary those
surfaces must consume; it does not create a second VOI or evidence subsystem.

Relevant anti-patterns:

- P01 contract-only capability: strategy enums or records are not enough
  unless a producer emits artifacts and consumers enforce the disposition.
- P05 authority dilution: acquisition routing cannot become legal, data,
  method, participation, claim-support, or closeout authority.
- P09 soft-gate ambiguity: accepted deficit, publish-with-limitation, and
  closeout block must remain distinct owned dispositions.
- P13 contract gravity well: VOI weights, thresholds, owners, and timeouts stay
  governed tuned config instead of structural truth.
- P14 raw count inflation: acquisition actions cannot inflate evidence strength
  until an admissible producer artifact exists.
- P15 LLM speculation laundering: LLM acquisition ideas remain candidates until
  eligibility and producer output validate them.

Existing anti-pattern found: acquisition and VOI primitives existed, but the
mandatory-gate decision boundary was not yet an accepted ADR that E10, E16, and
E17 could cite. That was a `contract_only`/`bridge_missing` decision risk.

Target correct pattern: an accepted structural ADR with an eligible strategy
matrix, decision-owner matrix, terminal disposition semantics, governed tuned
parameters, and explicit consumer-side evidence boundaries.

Missing capability labels after this ADR: `producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`, `surface_missing`,
and `semantic_test_missing` for the future acquisition planner capability.
Those labels are expected for W0.A because this phase ratifies the decision
boundary rather than implementing E17.

Acceptance signal: later work can cite ADR-0166, compute eligible strategies
before VOI ranking, and prove with a negative test that VOI cannot rank around
a non-overridable blocker.

## Consequences

Positive:

- Evidence gaps produce actionable next steps rather than generic failure.
- VOI remains useful without becoming a way to waive authority.
- Operators can see when the next action is acquire, rerun, proxy with
  limitation, accept deficit, or block.
- Acquisition outcomes can improve future routing and cost estimates without
  contaminating current-run evidence.
- E10, E16, and E17 get a common decision boundary.

Negative:

- Some runs that could produce plausible prose will block until the correct
  producer emits admissible evidence.
- Governed and production commits need owner plumbing and audit records.
- The eligibility matrix needs maintenance as new gap types or strategies
  become real.
- Advisory mode may initially surface more blockers than it resolves.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- an acquisition strategy enum and acquisition action record;
- `gap_type x authority_level x mandatory_gate_state` eligibility evaluation;
- decision-owner and commit-authority fields;
- terminal disposition fields for `accepted_deficit`,
  `publish_with_limitation`, and `closeout_block`;
- VOI integration that accepts only eligible strategies;
- public/readiness/closeout readers that preserve acquisition limitations and
  blockers;
- calibration feedback from acquisition outcomes to future strategy priors;
- negative tests for mandatory-gate bypass, broad-bundle source laundering,
  raw-file snapshot laundering, participation-prevalence laundering, and LLM
  recommendation laundering.

## Related Decisions

- Extends: ADR-0052 DataGap as a First-Class Object.
- Extends: ADR-0132 Scientist VOI Compute Law.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Extends: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
- Extends: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
- Extends: ADR-0164 Run Cost, Proportionality, And Evidence Budget Governance.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Related: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
