# ADR-0162: Human Oversight, Publication, And External Audit Authority

## Status

Accepted

## Date

2026-05-18

## Context

Pass 1B diagnostics found that tenant ownership, CAS ownership, approval,
human review, override, signing, public export, local-client evidence, and
external audit controls exist in pieces but do not form one publication
authority contract for a serious policy decision.

The Policy Design Case SDD requires publication authority to derive from the
case and the honest diagnostics substrate. It also requires effective human
oversight, producer independence, public contestability, publication trust, and
external audit evidence to be case records rather than side notes.

If implementation treats a human approval click, public packet hash, dashboard
state, or audit bundle as sufficient authority, PolicyOS will publish
official-looking decisions without proving that human oversight was effective
or that an external verifier can replay the evidence graph.

## Decision

1. Human oversight, producer independence, publication authority, public
   export, local/client evidence boundaries, and external audit are
   authority-bearing Policy Design Case records.
2. Governed and production publication require an effective human oversight
   record. The record includes reviewer identity or role, authority profile,
   reviewer independence, conflicts, review scope, dissent, challenge outcome,
   reviewer changes, override decision, rubber-stamp risk, automation-bias
   controls, exposure-order controls, VOI escalation, and accepted deficits.
3. Producer independence is a first-class closeout record. It discloses
   separation of duties, conflicts of interest, requester-capture challenge
   results, producer self-certification limits, and any case where one surface
   selected evidence, generated claims, and certified those claims.
4. Publication authority derives from Policy Design Case readiness, approval,
   and the honest diagnostics substrate. A public export, dashboard projection,
   signed file, client-local packet, or archive bundle cannot mint authority
   that the runtime case did not already have.
5. The publication trust record includes approval and override packet ids,
   signing material refs, release and topology provenance, dependency-rights
   status, privacy/security and redaction evidence, semantic-preservation proof,
   local/client evidence classification, archive/replay refs, and public
   contestability hooks.
6. External audit evidence must be replayable without private operator context
   except for explicitly redacted or access-controlled evidence. The audit
   record points to the core audit PROV/SLSA archive, standalone verifier
   command, safe archive location, evidence-rights map, and public/private
   evidence boundary.
7. Retraction, recall, amendment, and contestability hooks are recorded before
   publication so later lifecycle events can reference publication authority
   without rewriting historical state.
8. Scorecard and readiness gates must fail for governed and production
   publication when required oversight, independence, publication trust, public
   export, local/client boundary, or external audit records are missing,
   stale, contradictory, or projection-only.

## Consequences

Positive:

- Public-facing policy decisions become auditable governance objects rather
  than exported narratives.
- Human review quality can be inspected instead of inferred from an approval
  action.
- External auditors can replay the case authority chain and see which evidence
  was public, private, redacted, or rights-limited.
- Dashboard, client, public export, and archive surfaces keep projection and
  authority roles separate.

Negative:

- Publication requires more structured closeout evidence and may block when
  review telemetry or audit archives are incomplete.
- Human oversight instrumentation must avoid turning review-quality evidence
  into unnecessary surveillance.
- Some useful public artifacts will remain draft or projection-only until the
  case records prove publication trust.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- human oversight effectiveness records in or over `runtime/quality`;
- producer and reviewer independence records;
- publication trust and public export authority records;
- local/client evidence boundary classification;
- external audit archive refs using core audit PROV/SLSA verifier surfaces;
- readiness checks for rubber-stamp risk, missing independence, projection-only
  public packets, missing redaction proof, missing standalone verification, and
  missing recall/contestability hooks;
- dashboard/API/public labels for draft, projection-only, redacted, stale,
  contested, blocked, publishable, published, recalled, and retracted states.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Related: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.
- Related: ADR-0161 Claim Argument, Warrant Reliability, And Compiler Closeout
  Gate.
- Related: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
