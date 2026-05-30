# ADR-0170: Contestability And Recourse Boundaries

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution must stay contestable after a public
projection, export, dashboard card, or audit packet is produced. A case can be
blocked, limited, contested, stale, reissued, withdrawn, or published, but the
external surface must not imply that PolicyOS is the universal tribunal for
every affected institution.

The repository already has relevant surfaces: Policy Design Case projection
semantics, public export guards, human oversight and publication trust records,
append-only lifecycle ledgers, contestability appeal outcome provenance, and
scorecard/readiness authority boundaries. The missing decision is the boundary
between PolicyOS-owned contestability records and deployment-owned recourse
processes.

Stated directly: PolicyOS-owned contestability records are separate from
deployment-owned recourse processes.

Without this ADR, E4/E5 could expose contested records while pretending that a
projection owns the appeal process, or it could publish a high-stakes contested
production case without a usable recourse path. Both failures would recreate
P03, P05, and P10: hidden public-surface truth, authority dilution, and
structural validity without semantic adequacy.

This ADR ratifies W0.C FT-ADR-03 from the Universal Policy Design Case
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

1. PolicyOS owns contested records, public visibility, reopening triggers,
   `recourse_pointer`, and recourse-outcome ingestion.
2. Deployment-owned recourse processes own appeal intake, adjudication,
   statutory or institutional SLA authority, standing decisions, remedies, and
   escalation chains unless a deployment explicitly delegates one of those
   responsibilities to a governed PolicyOS workflow.
3. PolicyOS may record that a recourse process exists and was reachable. That
   record is not evidence that an appeal was fair, timely, or correctly
   adjudicated.
4. A contested record is a PolicyOS case record. It binds disagreement,
   rebuttal, public challenge, legal/participation dispute, or affected-person
   objection to case, claim, audience, authority profile, status, provenance,
   lifecycle effect, and public visibility.
5. `recourse_pointer` is a pointer record, not an adjudication record. It tells
   public, reviewer, expert, machine, dashboard, and audit consumers where a
   deployment-owned recourse process can be reached.
6. A verified-reachable recourse pointer means:
   - the pointer has a public `https` URI for the recourse entry point;
   - the pointer has `verification_status` equal to `reachable`,
     `verified`, or `verified_reachable`;
   - the pointer has `verified_at`;
   - the pointer has a `verification_ref`, `verification_event_ref`, or
     equivalent runtime evidence ref;
   - the pointer declares the authority boundary as deployment-owned recourse
     process rather than PolicyOS adjudication authority.
7. High-stakes contested production publication must fail closed when
   `recourse_pointer` is absent or unreachable. The canonical blocker code is
   `public_export_recourse_pointer_unreachable`.
8. Recourse outcomes can be ingested only as append-only lifecycle or
   institutional provenance records. They can reopen, reissue, stale, withdraw,
   amend, recall, or annotate affected case/claim scopes, but they do not
   rewrite historical publication authority.
9. LLM-generated objections, appeal suggestions, or recourse summaries are
   candidates only. They cannot satisfy contested-record evidence or
   `recourse_pointer` reachability.
10. Redaction may protect private identifiers, sensitive raw material, and
    private deliberation, but it may not hide contested state, blocker state,
    public recourse pointer status, or the fact that recourse is
    deployment-owned.

## Structural Commitment

Contestability and recourse implementation must model at least these
structural fields where the capability is in scope:

- `contested_record_id`
- `case_ref`
- `claim_refs`
- `audience_visibility`
- `contestability_status`
- `grounds`
- `standing_or_actor_ref`
- `counterevidence_refs`
- `source_truth_conflict_refs`
- `authority_profile`
- `publication_effect`
- `reopening_trigger_refs`
- `lifecycle_event_refs`
- `recourse_pointer`
- `recourse_pointer.uri`
- `recourse_pointer.verification_status`
- `recourse_pointer.verified_at`
- `recourse_pointer.verification_ref`
- `recourse_pointer.owner`
- `recourse_pointer.authority_boundary`
- `recourse_outcome_refs`
- `ingestion_event_refs`
- `public_projection_effect`

Consumer-side enforcement is required. A producer that emits a pointer-like
field is not enough. Public export, dashboard, API projection, and audit
surfaces must fail closed or surface a typed blocker when a high-stakes
contested production publication lacks a verified-reachable recourse pointer.

The initial runtime guard is
`polisyos.runtime.quality.contestability.verified_recourse_pointer_for_publication`,
consumed by public export construction. It is a narrow W0.C bridge so E4/E5 can
cite a ratified boundary before full typed projection DTOs land.

## Tuned Parameter

These values are deployment or governed configuration, not structural truth:

- appeal intake channel details;
- adjudicator, ombud, agency, court, or escalation owner;
- standing rules and evidence submission rules;
- appeal SLA, response deadline, retry cadence, and escalation threshold;
- jurisdiction-specific notice language;
- accessibility and language requirements;
- high-stakes classification thresholds when not already set by authority
  profile;
- verification cadence and automated reachability probe details.

Changing those values does not require a new ADR if PolicyOS still owns only
the contested record, public visibility, reopening trigger, recourse pointer,
and recourse-outcome ingestion boundary.

## Authority Boundary

Contestability records may be authoritative for:

- whether PolicyOS observed a contested case, claim, evidence line, public
  surface, or lifecycle state;
- which claims or audiences are affected;
- which recourse pointer was shown;
- whether the pointer had verified reachable status at the recorded time;
- which runtime event ingested a recourse outcome;
- which lifecycle effect PolicyOS applied after ingestion.

Contestability records may not be authoritative for:

- legal correctness of the underlying appeal;
- deployment-owned standing decisions;
- adjudication merits;
- statutory or institutional SLA compliance;
- remedy adequacy;
- claim support;
- legal authority;
- closeout pass.

Those authorities require their own producer records, legal/institutional
process evidence, or deployment/governed adjudication artifacts. A public
projection, export, or dashboard may show contested state, but it cannot
convert contested state into publication authority.

## Negative Laundering Test

Future implementation and current W0.C guardrails must include these minimum
cases:

The negative guard targets high-stakes contested production publication when a
pointer is absent or unreachable.

1. A high-stakes contested production publication with no `recourse_pointer`
   fails with `public_export_recourse_pointer_unreachable`.
2. A high-stakes contested production publication with a pointer whose
   `verification_status` is `unreachable`, `failed`, `unknown`, or absent also
   fails with the same blocker.
3. A public export that merely contains narrative appeal instructions cannot
   satisfy `recourse_pointer`.
4. A reachable pointer does not let PolicyOS claim appeal intake,
   adjudication, SLA authority, or remedy adequacy.
5. A recourse outcome ingestion event may move scoped lifecycle state to
   reissue, stale, withdrawal, amendment, recall, or annotation, but it cannot
   rewrite the original publication authority record.
6. An LLM-generated objection or appeal summary remains
   `candidate_unverified` until a deterministic or governed producer binds it
   to a contested record or lifecycle event.

## Feature Flag / Advisory Posture

Initial W0.C enforcement is narrow and fail-closed only for high-stakes
contested production publication surfaces:

- `universal_pdc_contestability_projection`: may expose contested records and
  pointer status as projection-only truth.
- `universal_pdc_recourse_pointer_publication_guard`: enabled for high-stakes
  contested production public export and compatible E4/E5 surfaces.
- `universal_pdc_recourse_outcome_ingestion`: advisory until E15 wires
  lifecycle ingestion over append-only case records.
- `universal_pdc_recourse_adjudication`: out of scope unless a deployment
  explicitly delegates adjudication authority and supplies a governed process.

Advisory or projection-only surfaces may help operators triage contested cases.
They cannot adjudicate, close, or publish a contested high-stakes production
case when the required pointer is missing or unreachable.

## Revision Path

A new ADR is required to:

- let PolicyOS own appeal intake, adjudication, SLA, or remedy authority by
  default;
- allow non-public or non-verified recourse pointers for high-stakes contested
  production publication;
- remove consumer-side enforcement for `recourse_pointer`;
- allow narrative appeal text, LLM output, or dashboard labels to satisfy
  `recourse_pointer`;
- allow recourse outcome ingestion to rewrite historical publication
  authority;
- change the blocker semantics of
  `public_export_recourse_pointer_unreachable`.

A governed configuration change is sufficient to tune deployment owner,
verification cadence, appeal SLA, standing rules, language/accessibility
requirements, or high-stakes classification details when the structural
boundary remains unchanged.

## Affected E Tasks

This ADR unblocks:

- E4 Typed PDC Projection, for C17/C39b contested records and
  `recourse_pointer` projection fields;
- E5 Client, Dashboard, Export, And Audit Surface, for public/reviewer/expert
  and machine visibility of contested state without adjudication authority;
- E15 Lifecycle/Reissue, for recourse-outcome ingestion and scoped lifecycle
  effects.

It also constrains:

- E3 closeout, because contested high-stakes production publication cannot
  close out without pointer evidence when contestability is in scope;
- E22 semantic evaluation, because unreachable recourse pointers are a
  content-level false-pass fixture;
- E23 docs/ADR/runbooks, because C39b must stay traceable to this boundary
  rather than being baked into projection code review.

## Validation

The ADR itself is validated by docs lifecycle and ADR index gates:

```bash
uv run pytest tests/repo_quality/tools/test_policy_design_case_w0c_contestability.py -q
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

The W0.C negative publication guard is validated by:

```bash
uv run pytest tests/unit/runtime/quality/test_public_export.py::test_public_export_blocks_high_stakes_contested_production_without_reachable_recourse -q
```

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. Public export guards, PDC projection
semantics, lifecycle ledgers, human-oversight publication records, and
institutional provenance are the right owners. This ADR adds the
contestability/recourse ownership boundary and a narrow public-export guard.

Relevant anti-patterns:

- P03 poor external surface: public, reviewer, expert, machine, dashboard, and
  audit surfaces must expose contested state and pointer status.
- P05 authority dilution: a recourse pointer is not appeal intake,
  adjudication, SLA, remedy, closeout, or claim-support authority.
- P09 warning lifecycle gap: contested records, reopening triggers, and
  recourse outcomes need lifecycle effects rather than narrative notes.
- P10 structural-only validation: high-stakes contested production publication
  must fail on missing or unreachable recourse, not merely validate shape.
- P15 LLM speculation laundering: appeal suggestions or objection summaries
  remain candidates until a governed producer binds them to a record.

Existing anti-pattern found: contested/public projection surfaces could expose
or omit recourse semantics without a ratified owner boundary. That was a
`surface_missing`/`semantic_test_missing` risk for C17 and C39b.

Target correct pattern: PolicyOS owns contested records, public visibility,
reopening triggers, `recourse_pointer`, and append-only outcome ingestion, while
deployment processes own appeal intake, adjudication, SLA, standing, and
remedy authority.

Missing capability labels after this ADR and W0.C guard:
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
and `semantic_test_missing` for full contested-record and recourse-outcome
lifecycle ingestion. The public-export guard closes the immediate high-stakes
publication false pass, but E4/E5 and E15 still need typed end-to-end records.

Acceptance signal: later work can cite ADR-0170, reject high-stakes contested
production publication without a verified-reachable pointer, and ingest
deployment recourse outcomes only as append-only lifecycle/provenance effects.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Extends: ADR-0162 Human Oversight, Publication, And External Audit
  Authority.
- Extends: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
- Related: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Related: ADR-0166 Evidence Acquisition Decision Boundaries.
